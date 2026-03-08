import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ChatMessage } from './chat-message';

describe('ChatMessage', () => {
  let component: ChatMessage;
  let fixture: ComponentFixture<ChatMessage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ChatMessage]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ChatMessage);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
