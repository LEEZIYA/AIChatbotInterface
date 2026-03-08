import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';

import { Header } from './components/header/header'
import { AgentSelector } from './components/agent-selector/agent-selector';
import { ChatWindow } from './components/chat-window/chat-window';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet,
    MatToolbarModule,
    Header,
    AgentSelector,
    ChatWindow
  ],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
  protected readonly title = signal('multi-agent-chat');
}
