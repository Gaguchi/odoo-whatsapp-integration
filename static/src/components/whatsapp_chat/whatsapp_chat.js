/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
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
        this.messagesEndRef = useRef("messagesEnd");

        this.state = useState({
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
            await this.loadConversations();
            // Check if we should open a specific conversation
            const activeId = this.props.action?.context?.active_conversation_id;
            if (activeId) {
                await this.selectConversation(activeId);
            }
        });

        onMounted(() => {
            this.scrollToBottom();
        });
    }

    async loadConversations() {
        this.state.loading = true;
        try {
            const conversations = await this.orm.searchRead(
                "whatsapp.conversation",
                [],
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

        try {
            // Get the default account
            const [account] = await this.orm.searchRead(
                "whatsapp.account",
                [],
                ["id"],
                { limit: 1 }
            );

            if (!account) {
                this.notification.add(_t("No WhatsApp account configured"), { type: "warning" });
                return;
            }

            // Create or get conversation
            const conversationId = await this.orm.call(
                "whatsapp.conversation",
                "get_or_create",
                [account.id, this.state.newChatPhone.trim()]
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
