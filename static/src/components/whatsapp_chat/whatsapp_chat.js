/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class WhatsAppChat extends Component {
    static template = "whatsapp_integration.WhatsAppChat";
    static props = {
        action: { type: Object, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.busService = useService("bus_service");
        this.messagesEndRef = useRef("messagesEnd");
        this.pollInterval = null;

        this.state = useState({
            accounts: [],
            selectedAccountId: null,
            conversations: [],
            activeConversation: null,
            messages: [],
            newMessage: "",
            loading: false,
            sendingMessage: false,
            showNewChatDialog: false,
            newChatPhone: "",
        });

        onWillStart(async () => {
            await this.loadAccounts();
            await this.loadConversations();
            // Check if we should open a specific conversation
            const activeId = this.props.action?.context?.active_conversation_id;
            if (activeId) {
                await this.selectConversation(activeId);
            }
        });

        onMounted(() => {
            this.scrollToBottom();
            // Subscribe to bus for real-time updates
            this.subscribeToChannels();
            // Start fallback polling (less frequent since we have bus)
            this.startFallbackPolling();
        });

        onWillUnmount(() => {
            this.stopFallbackPolling();
        });
    }

    subscribeToChannels() {
        // Subscribe to all account channels for this user
        for (const account of this.state.accounts) {
            const channel = `whatsapp_channel_${account.id}`;
            this.busService.subscribe(channel, (payload) => {
                this.onBusNotification(payload);
            });
        }
    }

    onBusNotification(payload) {
        console.log("WhatsApp bus notification:", payload);

        if (payload.type === 'new_message') {
            // Handle new incoming message
            const accountId = payload.account_id;
            const conversationId = payload.conversation_id;
            const message = payload.message;

            // If it's for the currently selected account, update UI
            if (accountId === this.state.selectedAccountId) {
                // Refresh conversation list to show new message preview
                this.loadConversations();

                // If this message is for the active conversation, add it
                if (this.state.activeConversation &&
                    this.state.activeConversation.id === conversationId) {
                    // Check if message already exists (avoid duplicates)
                    const exists = this.state.messages.some(m => m.id === message.id);
                    if (!exists) {
                        // Replace array to ensure OWL reactivity triggers
                        this.state.messages = [...this.state.messages, message];
                        setTimeout(() => this.scrollToBottom(), 100);
                        console.log("Message added to chat:", message);
                    }
                }
            }

            // Show notification for new message
            this.notification.add(
                _t("New message from ") + message.phone_number,
                { type: "info", sticky: false }
            );
        } else if (payload.type === 'status_update') {
            // Handle status update for existing message
            const messageId = payload.message_id;
            const newStatus = payload.status;

            // Update message status in current list
            const msg = this.state.messages.find(m => m.id === messageId);
            if (msg) {
                msg.status = newStatus;
                if (payload.error_message) {
                    msg.error_message = payload.error_message;
                }
            }
        }
    }

    startFallbackPolling() {
        // Reduced frequency since we have real-time bus updates
        // This is just a fallback in case bus misses something
        this.pollInterval = setInterval(async () => {
            if (!this.state.loading) {
                await this.loadConversations();
            }
        }, 30000); // Every 30 seconds
    }

    stopFallbackPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }

    async loadAccounts() {
        try {
            const accounts = await this.orm.searchRead(
                "whatsapp.account",
                [["active", "=", true]],
                ["id", "name", "state"],
                { order: "name asc" }
            );
            this.state.accounts = accounts;
            // Auto-select first account if none selected
            if (accounts.length > 0 && !this.state.selectedAccountId) {
                this.state.selectedAccountId = accounts[0].id;
            }
        } catch (error) {
            this.notification.add(_t("Failed to load accounts"), { type: "danger" });
            console.error(error);
        }
    }

    async onAccountChange(ev) {
        const accountId = parseInt(ev.target.value, 10);
        this.state.selectedAccountId = accountId;
        this.state.activeConversation = null;
        this.state.messages = [];
        await this.loadConversations();
    }

    async loadConversations() {
        this.state.loading = true;
        try {
            const domain = this.state.selectedAccountId
                ? [["account_id", "=", this.state.selectedAccountId]]
                : [];
            const conversations = await this.orm.searchRead(
                "whatsapp.conversation",
                domain,
                ["id", "display_name", "phone_number", "last_message_date", "last_message_preview", "unread_count"],
                { order: "last_message_date desc" }
            );
            this.state.conversations = conversations;
        } catch (error) {
            this.notification.add(_t("Failed to load conversations"), { type: "danger" });
            console.error(error);
        }
        this.state.loading = false;
    }

    async selectConversation(conversationId) {
        const conversation = this.state.conversations.find(c => c.id === conversationId);
        if (!conversation) {
            // Load conversation if not in list
            const [conv] = await this.orm.searchRead(
                "whatsapp.conversation",
                [["id", "=", conversationId]],
                ["id", "display_name", "phone_number", "last_message_date", "last_message_preview", "unread_count"]
            );
            if (conv) {
                this.state.activeConversation = conv;
            }
        } else {
            this.state.activeConversation = conversation;
        }

        if (this.state.activeConversation) {
            await this.loadMessages();
        }
    }

    async loadMessages() {
        if (!this.state.activeConversation) return;

        try {
            const messages = await this.orm.call(
                "whatsapp.conversation",
                "get_messages",
                [this.state.activeConversation.id]
            );
            this.state.messages = messages;
            // Scroll to bottom after messages load
            setTimeout(() => this.scrollToBottom(), 100);
        } catch (error) {
            this.notification.add(_t("Failed to load messages"), { type: "danger" });
            console.error(error);
        }
    }

    scrollToBottom() {
        if (this.messagesEndRef.el) {
            this.messagesEndRef.el.scrollIntoView({ behavior: "smooth" });
        }
    }

    onMessageInput(ev) {
        this.state.newMessage = ev.target.value;
    }

    onKeyPress(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    async sendMessage() {
        if (!this.state.newMessage.trim() || !this.state.activeConversation) return;

        this.state.sendingMessage = true;
        try {
            const result = await this.orm.call(
                "whatsapp.conversation",
                "send_message",
                [this.state.activeConversation.id, this.state.newMessage]
            );

            // Add message to list
            this.state.messages.push(result);
            this.state.newMessage = "";

            // Update conversation preview
            await this.loadConversations();

            // Scroll to bottom
            setTimeout(() => this.scrollToBottom(), 100);

            if (result.status === "failed") {
                this.notification.add(_t("Message failed to send: ") + result.error_message, { type: "danger" });
            }
        } catch (error) {
            this.notification.add(_t("Failed to send message"), { type: "danger" });
            console.error(error);
        }
        this.state.sendingMessage = false;
    }

    toggleNewChatDialog() {
        this.state.showNewChatDialog = !this.state.showNewChatDialog;
        this.state.newChatPhone = "";
    }

    onNewChatPhoneInput(ev) {
        this.state.newChatPhone = ev.target.value;
    }

    async startNewChat() {
        if (!this.state.newChatPhone.trim()) return;

        if (!this.state.selectedAccountId) {
            this.notification.add(_t("Please select a WhatsApp account first"), { type: "warning" });
            return;
        }

        try {
            // Create or get conversation using the selected account
            const conversationId = await this.orm.call(
                "whatsapp.conversation",
                "get_or_create",
                [this.state.selectedAccountId, this.state.newChatPhone.trim()]
            );

            // Reload conversations and select the new one
            await this.loadConversations();
            await this.selectConversation(conversationId);

            this.state.showNewChatDialog = false;
            this.state.newChatPhone = "";
        } catch (error) {
            this.notification.add(_t("Failed to start new chat"), { type: "danger" });
            console.error(error);
        }
    }

    formatTime(isoString) {
        if (!isoString) return "";
        const date = new Date(isoString);
        const now = new Date();
        const isToday = date.toDateString() === now.toDateString();

        if (isToday) {
            return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        }
        return date.toLocaleDateString([], { month: "short", day: "numeric" });
    }

    getStatusIcon(status) {
        switch (status) {
            case "sent": return "fa-check";
            case "delivered": return "fa-check-double";
            case "read": return "fa-check-double text-primary";
            case "failed": return "fa-times text-danger";
            default: return "fa-clock-o";
        }
    }
}

registry.category("actions").add("whatsapp_chat", WhatsAppChat);
