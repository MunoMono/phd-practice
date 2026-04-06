import React, { useEffect, useRef, useState } from 'react';
import {
  Tile,
  TextArea,
  Button,
  Tag,
  InlineLoading,
} from '@carbon/react';
import { SendAlt } from '@carbon/icons-react';

// Extract usable citation info from a context chunk
function extractSourceInfo(chunk) {
  const text = chunk.text || '';
  const citation = chunk.citation || '';

  // PID from citation like "pid_abc123_xyz, p.?" -> "pid_abc123_xyz"
  const pid = citation.split(',')[0].trim();

  // First speaker name from "## SPEAKERS" block
  let speaker = null;
  const speakersMatch = text.match(/##\s+SPEAKERS\s*\n+([^\n]+)/);
  if (speakersMatch) {
    speaker = speakersMatch[1].split(',')[0].trim();
  }

  // First spoken quote: text after a "## SpeakerName HH:MM" heading
  let quote = null;
  const lines = text.split('\n');
  for (let i = 0; i < lines.length - 1; i++) {
    const line = lines[i].trim();
    if (/^## .+ \d+:\d+$/.test(line)) {
      const parts = [];
      for (let j = i + 1; j < lines.length; j++) {
        const next = lines[j].trim();
        if (next.startsWith('##') || next.startsWith('--')) break;
        if (next) parts.push(next);
      }
      const raw = parts.join(' ');
      if (raw.length >= 20) {
        quote = raw.length > 130 ? raw.slice(0, 130) + '\u2026' : raw;
        break;
      }
    }
  }

  return { speaker, pid, quote };
}

const GraniteChatPanel = () => {
  const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Ask Granite a question about the ingested archive transcripts.',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const historyRef = useRef(null);

  useEffect(() => {
    if (!historyRef.current) {
      return;
    }

    historyRef.current.scrollTop = historyRef.current.scrollHeight;
  }, [messages, loading]);

  const handleSubmit = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) {
      return;
    }

    const userMessage = {
      role: 'user',
      content: trimmed,
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const requestUrl = `${API_BASE}/api/granite/analyze`;
      console.log('Granite chat request URL:', requestUrl);

      const response = await fetch(requestUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: trimmed }),
      });

      console.log('Granite chat response status:', response.status);

      const contentType = response.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        const rawResponseText = await response.text();
        console.error('Granite chat non-JSON response:', rawResponseText);
        throw new Error('Server returned non-JSON response');
      }

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail || payload.message || `Request failed with status ${response.status}`);
      }

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: payload.analysis || 'No analysis returned.',
          numContextChunks: payload.num_context_chunks,
          inferenceTimeSeconds: payload.inference_time_seconds,
          contextChunks: payload.context_chunks || [],
        },
      ]);
    } catch (error) {
      console.error('Granite chat request failed:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `Backend error: ${errorMessage}`,
          isError: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  return (
    <Tile className="granite-chat-tile">
      <div className="granite-chat__header">
        <div>
          <h4>Granite archive chat</h4>
          <p>Query the ingested transcripts directly from the dashboard.</p>
        </div>
        <Tag type="blue">IBM Granite</Tag>
      </div>

      <div className="granite-chat__history" ref={historyRef} aria-live="polite">
        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}-${message.content.slice(0, 24)}`}
            className={`granite-chat__message granite-chat__message--${message.role}`}
          >
            <div className="granite-chat__message-head">
              <Tag type={message.role === 'user' ? 'cool-gray' : message.isError ? 'red' : 'green'}>
                {message.role === 'user' ? 'You' : message.isError ? 'Error' : 'Granite'}
              </Tag>
            </div>
            <div className="granite-chat__message-body">{message.content}</div>
            {message.role === 'assistant' && !message.isError && (
              <div className="granite-chat__meta">
                {typeof message.numContextChunks === 'number' && (
                  <span>Chunks used: {message.numContextChunks}</span>
                )}
                {typeof message.inferenceTimeSeconds === 'number' && (
                  <span>Inference time: {message.inferenceTimeSeconds.toFixed(2)}s</span>
                )}
              </div>
            )}
            {message.role === 'assistant' && !message.isError && message.contextChunks?.length > 0 && (() => {
              const seenPids = new Set();
              const excerpts = message.contextChunks
                .map(chunk => ({ chunk, ...extractSourceInfo(chunk) }))
                .filter(({ pid, quote }) => {
                  if (!quote || seenPids.has(pid)) return false;
                  seenPids.add(pid);
                  return true;
                })
                .slice(0, 3);
              if (excerpts.length === 0) return null;
              return (
                <div className="granite-chat__sources">
                  <span className="granite-chat__sources-label">Source excerpts:</span>
                  <ul className="granite-chat__source-list">
                    {excerpts.map(({ chunk, speaker, pid, quote }, i) => (
                      <li key={chunk.id || i} className="granite-chat__source-item">
                        <span className="granite-chat__source-quote">“{quote}”</span>
                        {(speaker || pid) && (
                          <span className="granite-chat__source-ref">
                            {' — '}
                            {speaker && <span>{speaker}</span>}
                            {pid && <span className="granite-chat__source-pid"> ({pid})</span>}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })()}
          </div>
        ))}

        {loading && (
          <div className="granite-chat__loading">
            <InlineLoading description="Waiting for Granite response..." status="active" />
          </div>
        )}
      </div>

      <div className="granite-chat__composer">
        <TextArea
          id="granite-chat-input"
          labelText="Ask about the archive"
          hideLabel
          placeholder="Ask a question about the transcripts"
          rows={3}
          value={input}
          onChange={event => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <Button
          kind="primary"
          size="md"
          renderIcon={SendAlt}
          onClick={handleSubmit}
          disabled={loading || !input.trim()}
        >
          {loading ? 'Sending...' : 'Send'}
        </Button>
      </div>
    </Tile>
  );
};

export default GraniteChatPanel;