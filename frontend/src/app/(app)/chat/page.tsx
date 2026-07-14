import { ChatWindow } from "@/components/chat/ChatWindow";

export const metadata = { title: "Chat" };

export default function ChatPage() {
  return <ChatWindow conversationId={null} />;
}
