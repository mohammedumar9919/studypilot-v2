import { useState } from 'react'

import { CourseOutlineSidebar } from './components/CourseOutlineSidebar'
import { AnswerPanel } from './components/AnswerPanel'
import { ChunkInspector } from './components/ChunkInspector'
import { DebugPanel } from './components/DebugPanel'
import { IngestBanner } from './components/IngestBanner'
import { ProgressIndicator } from './components/ProgressIndicator'
import { QueryForm } from './components/QueryForm'
import { TopicFrequencyPanel } from './components/TopicFrequencyPanel'
import { TocBrowser } from './components/TocBrowser'
import { TrustBadges } from './components/TrustBadges'
import { useStudyQuery } from './hooks/useStudyQuery'
import type { GoldenMissHint } from './types'
import './App.css'

function App() {
  const [courseId, setCourseId] = useState('PPL')
  const [question, setQuestion] = useState('')
  const [debugEnabled, setDebugEnabled] = useState(false)
  const [selectedHint, setSelectedHint] = useState<GoldenMissHint | null>(null)
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null)

  const { stage, elapsedMs, result, error, streamNotice, submit } = useStudyQuery()
  const loading = stage === 'retrieving' || stage === 'generating'
  const isStreaming = stage === 'generating'

  const handleSubmit = () => {
    setSelectedChunkId(null)
    void submit(
      {
        course_id: courseId.trim(),
        question: question.trim(),
        debug: debugEnabled,
      },
      { useStream: !debugEnabled },
    )
  }

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>StudyPilot v2</h1>
          <p className="subtitle">Ask your course notes — cited answers from your PDFs</p>
        </div>
      </header>

      {!debugEnabled && <IngestBanner />}

      <main className="app-main">
        <div className="column column-primary">
          <QueryForm
            courseId={courseId}
            question={question}
            debugEnabled={debugEnabled}
            loading={loading}
            onCourseIdChange={setCourseId}
            onQuestionChange={setQuestion}
            onDebugChange={setDebugEnabled}
            onSubmit={handleSubmit}
          />

          <ProgressIndicator stage={stage} elapsedMs={elapsedMs} />

          {streamNotice && (
            <p className="stream-notice muted" role="status">
              {streamNotice}
            </p>
          )}

          {error && (
            <section className="panel error-panel" role="alert">
              <h2>Error</h2>
              <p>{error}</p>
            </section>
          )}

          {result && <AnswerPanel result={result} isStreaming={isStreaming} />}
        </div>

        <div className="column column-secondary">
          <CourseOutlineSidebar courseId={courseId} onSectionSelect={setQuestion} />

          <TopicFrequencyPanel courseId={courseId} />

          {debugEnabled && (
            <>
              <TocBrowser
                chunks={result?.retrieval_debug?.chunks ?? []}
                selectedChunkId={selectedChunkId}
                onSelectChunkId={setSelectedChunkId}
              />

              <ChunkInspector
                selectedHint={selectedHint}
                onSelectHint={setSelectedHint}
                onLoadQuestion={setQuestion}
                result={result}
                debugEnabled={debugEnabled}
                selectedChunkId={selectedChunkId}
                onSelectChunkId={setSelectedChunkId}
              />

              {result && <DebugPanel result={result} />}
            </>
          )}
        </div>
      </main>

      <footer className="app-footer">
        <TrustBadges />
        {debugEnabled && <span className="footer-dev-note">Developer mode — API proxy → localhost:8001</span>}
      </footer>
    </div>
  )
}

export default App
