import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AgentSelector } from './agent-selector';

describe('AgentSelector', () => {
  let component: AgentSelector;
  let fixture: ComponentFixture<AgentSelector>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AgentSelector]
    })
    .compileComponents();

    fixture = TestBed.createComponent(AgentSelector);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
