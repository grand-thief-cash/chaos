export interface BufferStats {
  key: string;
  category: string;
  submitted_rows: number;
  flushed_rows: number;
  pending_items: number;
  flush_count: number;
}

export interface WriteBufferStatus {
  enabled: boolean;
  buffers: BufferStats[];
}

