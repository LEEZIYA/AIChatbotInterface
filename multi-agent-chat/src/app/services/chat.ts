import { Injectable } from '@angular/core';
import { Subject, Observable } from 'rxjs';
import { ChatMessage } from '../models/chat-message';

@Injectable({ providedIn: 'root' })
export class ChatService {
  private messageSubject = new Subject<ChatMessage>();

  sendMessage(msg: ChatMessage): void {
    this.messageSubject.next(msg);
  }

  getMessages(): Observable<ChatMessage> {
    return this.messageSubject.asObservable();
  }
}