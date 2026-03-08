export interface ChatMessage {
  id: string;
  senderId: string;
  senderType: 'user' | 'agent' | 'system';
  receiverId?: string;
  content: string;
  timestamp: Date;
}