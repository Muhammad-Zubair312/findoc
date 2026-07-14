import { ChatWindow } from "@/components/chat/ChatWindow";

interface Props {
  params: { conversationId: string };
}

export function generateMetadata({ params }: Props) {
  return { title: `Chat · ${params.conversationId.slice(0, 8)}` };
}

export default function ConversationPage({ params }: Props) {
  return <ChatWindow conversationId={params.conversationId} />;
}
