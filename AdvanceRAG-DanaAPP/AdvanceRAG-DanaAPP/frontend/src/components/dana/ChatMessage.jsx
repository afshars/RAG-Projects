import React from 'react';
import { Sparkles, User } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import CitationsExpander from './CitationsExpander';
import FeedbackButtons from './FeedbackButtons';
import ConfidenceBadge from './ConfidenceBadge';

export default function ChatMessage({ message, onFeedback, onDetailedFeedback }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 animate-slide-up ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center ${
          isUser
            ? 'bg-muted text-muted-foreground'
            : 'bg-primary text-primary-foreground shadow-md shadow-primary/20'
        }`}
      >
        {isUser ? <User className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
      </div>

      {/* Content */}
      <div className={`flex flex-col gap-1 max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        <span className="text-xs font-medium text-muted-foreground px-1">
          {isUser ? 'شما' : 'دانا'}
        </span>

        {/* Text */}
        {message.content && (
          <div
            className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              isUser
                ? 'bg-secondary text-black rounded-tr-sm'
                : 'bg-white border border-border shadow-sm text-foreground rounded-tl-sm'
            }`}
          >
            {isUser ? (
              <span className="whitespace-pre-wrap">{message.content}</span>
            ) : (
              <div
                className={`markdown-body ${message.streaming ? 'streaming-cursor' : ''}`}
              >
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
            )}
          </div>
        )}

        {/* Loading indicator */}
        {message.role === 'assistant' && !message.content && message.loading && (
          <div className="rounded-2xl rounded-tl-sm px-4 py-3 bg-white border border-border shadow-sm">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-primary/40 animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 rounded-full bg-primary/80 animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        )}

        {/* Citations + Feedback (only after streaming) */}
        {!isUser && !message.streaming && message.content && (
          <>
            {message.confidence && <ConfidenceBadge confidence={message.confidence} />}
            {message.sources && message.sources.length > 0 && (
              <CitationsExpander sources={message.sources} />
            )}
            <FeedbackButtons
              text={message.content}
              currentFeedback={message.feedback}
              onFeedback={(type) => onFeedback(message.id, type)}
              detailedFeedback={message.detailedFeedback}
              onDetailedFeedback={onDetailedFeedback ? (scores) => onDetailedFeedback(message.id, scores) : undefined}
            />
          </>
        )}
      </div>
    </div>
  );
}
