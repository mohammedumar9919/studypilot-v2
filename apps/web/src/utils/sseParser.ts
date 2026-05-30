export interface ParsedSseEvent {
  event: string
  data: unknown
}

/** Split buffered SSE text into complete frames (separated by blank lines). */
export function splitSseFrames(buffer: string): { frames: string[]; remainder: string } {
  const parts = buffer.split('\n\n')
  const remainder = parts.pop() ?? ''
  const frames = parts.map((frame) => frame.trim()).filter(Boolean)
  return { frames, remainder }
}

/** Parse one SSE frame block into event name + JSON data payload. */
export function parseSseFrame(frame: string): ParsedSseEvent {
  let event = 'message'
  let dataText = ''

  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataText = line.slice('data:'.length).trim()
    }
  }

  if (!dataText) {
    throw new Error('SSE frame missing data payload')
  }

  return { event, data: JSON.parse(dataText) as unknown }
}
