export default function TypingIndicator() {
  return (
    <div className="message-row message-row--agent" aria-label="Agent is typing">
      <div className="avatar" aria-hidden="true">NS</div>
      <div className="bubble bubble--agent bubble--typing">
        <span className="dot" />
        <span className="dot" />
        <span className="dot" />
      </div>
    </div>
  )
}
