import { useCallback, useState } from 'react'

import { StudyJourneyStrip } from './components/StudyJourneyStrip'
import { CourseOutlineSidebar } from './components/CourseOutlineSidebar'
import { AnswerPanel } from './components/AnswerPanel'
import { ChunkInspector } from './components/ChunkInspector'
import { DebugPanel } from './components/DebugPanel'
import { DocumentUploadPanel } from './components/DocumentUploadPanel'
import { EmptyCourseState } from './components/EmptyCourseState'
import { ProgressIndicator } from './components/ProgressIndicator'
import { QueryForm } from './components/QueryForm'
import { TopicFrequencyPanel } from './components/TopicFrequencyPanel'
import { TocBrowser } from './components/TocBrowser'
import { TrustBadges } from './components/TrustBadges'
import { useStudyQuery } from './hooks/useStudyQuery'
import type { DocumentUploadResponse, GoldenMissHint, UploadPanelPhase } from './types'
import './App.css'
import './wave4a-theme.css'

function App() {
  const [courseId, setCourseId] = useState('PPL')
  const [question, setQuestion] = useState('')
  const [debugEnabled, setDebugEnabled] = useState(false)
  const [selectedHint, setSelectedHint] = useState<GoldenMissHint | null>(null)
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState(0)
  const [uploadIndexing, setUploadIndexing] = useState(false)
  const [courseHasDocuments, setCourseHasDocuments] = useState<boolean | null>(null)

  const { stage, elapsedMs, result, error, streamNotice, submit } = useStudyQuery()
  const loading = stage === 'retrieving' || stage === 'generating'
  const isStreaming = stage === 'generating'

  const handleOutlineState = useCallback(
    (state: { loaded: boolean; notFound: boolean; hasData: boolean }) => {
      if (!state.loaded) return
      setCourseHasDocuments(state.hasData)
    },
    [],
  )

  const handleUploadSuccess = (_response: DocumentUploadResponse) => {
    setCourseHasDocuments(true)
    setRefreshToken((token) => token + 1)
  }

  const handleUploadPhaseChange = (phase: UploadPanelPhase) => {
    setUploadIndexing(phase === 'indexing')
  }

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

  const showEmptyState =
    !debugEnabled && courseHasDocuments === false && !loading && !result && !uploadIndexing

  return (
    <div className="app-shell">
      <div className="ambient-streaks" aria-hidden="true" />
      <div className="app">
        <header className="app-header reveal-on-load">
          <div className="app-header-main">
            <h1>
              Study<span className="gradient-accent">Pilot</span>
            </h1>
            <p className="subtitle">Ask your course notes — cited answers from your PDFs</p>
          </div>
          <TrustBadges />
        </header>

        <StudyJourneyStrip
          stage={stage}
          hasSources={Boolean(result?.sources.length)}
          hasAnswer={Boolean(result?.answer?.length)}
          uploadIndexing={uploadIndexing}
        />

        <main className="app-main reveal-on-load reveal-delay-1">
          <div className="column column-primary">
            {!debugEnabled && (
              <DocumentUploadPanel
                courseId={courseId}
                disabled={loading}
                onUploadSuccess={handleUploadSuccess}
                onPhaseChange={handleUploadPhaseChange}
              />
            )}

            {showEmptyState && <EmptyCourseState />}

            <QueryForm
              courseId={courseId}
              question={question}
              debugEnabled={debugEnabled}
              loading={loading || uploadIndexing}
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
            <CourseOutlineSidebar
              courseId={courseId}
              refreshToken={refreshToken}
              onSectionSelect={setQuestion}
              onOutlineState={handleOutlineState}
            />

            <TopicFrequencyPanel courseId={courseId} refreshToken={refreshToken} />

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
          {debugEnabled && (
            <span className="footer-dev-note">Developer mode — API proxy → localhost:8001</span>
          )}
        </footer>
      </div>
    </div>
  )
}

export default App
