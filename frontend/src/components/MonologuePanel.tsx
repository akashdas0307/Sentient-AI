import React, { useState, useEffect } from 'react';
import { Brain, Moon, ChevronDown, ChevronRight } from 'lucide-react';
import { useSentientStore } from '../store/useSentientStore';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface MonologuePanelProps {
  mobile?: boolean;
}

export const MonologuePanel: React.FC<MonologuePanelProps> = ({ mobile = false }) => {
  const monologueEntries = useSentientStore((s) => s.monologueEntries);
  const [isExpanded, setIsExpanded] = useState(!mobile);
  const [unreadCount, setUnreadCount] = useState(0);

  // Track new entries when collapsed
  useEffect(() => {
    if (!isExpanded) {
      setUnreadCount((prev) => prev + 1);
    } else {
      setUnreadCount(0);
    }
  }, [monologueEntries.length, isExpanded]);

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const truncateText = (text: string, maxLength: number) => {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + '...';
  };

  // Mobile floating button
  if (mobile) {
    return (
      <>
        <Button
          variant="default"
          size="icon"
          className={cn(
            "h-12 w-12 rounded-full shadow-lg bg-primary hover:bg-primary/90",
            unreadCount > 0 && "animate-pulse"
          )}
          onClick={() => setIsExpanded(true)}
        >
          <Brain size={20} />
          {unreadCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -top-1 -right-1 h-5 w-5 p-0 flex items-center justify-center text-[10px]"
            >
              {unreadCount > 9 ? '9+' : unreadCount}
            </Badge>
          )}
        </Button>

        {/* Mobile overlay */}
        {isExpanded && (
          <div
            className="fixed inset-0 z-50 bg-black/50"
            onClick={() => setIsExpanded(false)}
          >
            <Card
              className="absolute bottom-20 right-4 left-4 max-h-[60vh] bg-card border-border"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between p-4 border-b border-border">
                <div className="flex items-center gap-2">
                  <Brain size={16} className="text-primary" />
                  <span className="text-sm font-medium">Inner Monologue</span>
                  <Badge variant="outline" className="text-[10px] h-4 px-1.5">
                    {monologueEntries.length}
                  </Badge>
                </div>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setIsExpanded(false)}
                >
                  <ChevronDown size={16} />
                </Button>
              </div>
              <ScrollArea className="max-h-[calc(60vh-60px)]">
                <div className="p-3 space-y-2">
                  {monologueEntries.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No thoughts yet
                    </p>
                  ) : (
                    [...monologueEntries].reverse().map((entry) => (
                      <MonologueEntryCard
                        key={entry.id}
                        entry={entry}
                        formatTime={formatTime}
                        truncateText={truncateText}
                      />
                    ))
                  )}
                </div>
              </ScrollArea>
            </Card>
          </div>
        )}
      </>
    );
  }

  // Desktop panel
  return (
    <div className="h-full flex flex-col bg-card/30">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain size={14} className="text-primary" />
          <span className="text-xs font-medium uppercase tracking-wider">Inner Monologue</span>
          {!isExpanded && unreadCount > 0 && (
            <Badge variant="destructive" className="h-4 px-1.5 text-[10px]">
              {unreadCount}
            </Badge>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => setIsExpanded(!isExpanded)}
          className="h-6 w-6"
        >
          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </Button>
      </div>

      {isExpanded ? (
        <ScrollArea className="flex-1">
          <div className="p-3 space-y-2">
            {monologueEntries.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-6 opacity-50">
                Cognitive processes will appear here...
              </p>
            ) : (
              monologueEntries.map((entry) => (
                <MonologueEntryCard
                  key={entry.id}
                  entry={entry}
                  formatTime={formatTime}
                  truncateText={truncateText}
                />
              ))
            )}
          </div>
        </ScrollArea>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-[10px] text-muted-foreground uppercase tracking-widest opacity-30">
            Collapsed
          </p>
        </div>
      )}
    </div>
  );
};

interface MonologueEntryCardProps {
  entry: {
    id: string;
    monologue: string;
    is_daydream: boolean;
    decision_count: number;
    duration_ms: number | null;
    timestamp: number;
  };
  formatTime: (ts: number) => string;
  truncateText: (text: string, max: number) => string;
}

const MonologueEntryCard: React.FC<MonologueEntryCardProps> = ({
  entry,
  formatTime,
  truncateText,
}) => {
  return (
    <Card className="bg-card/50 border-border p-2.5 text-xs">
      <div className="flex items-start gap-2">
        <span className="text-base leading-none mt-0.5">
          {entry.is_daydream ? '🌙' : '💭'}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-[10px] text-muted-foreground mb-1">
            <span>{entry.is_daydream ? 'daydreaming' : 'thinking'}</span>
            <span>•</span>
            <span>{formatTime(entry.timestamp)}</span>
            {entry.decision_count > 0 && (
              <>
                <span>•</span>
                <span>{entry.decision_count} decisions</span>
              </>
            )}
            {entry.duration_ms !== null && (
              <>
                <span>•</span>
                <span>{entry.duration_ms}ms</span>
              </>
            )}
          </div>
          <p className="text-xs leading-relaxed text-foreground/80">
            {truncateText(entry.monologue, 200)}
          </p>
        </div>
      </div>
    </Card>
  );
};
