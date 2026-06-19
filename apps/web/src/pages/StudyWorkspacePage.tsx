import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { StudyJourneyStrip } from '../components/StudyJourneyStrip'
import { CourseMapTabPanel } from '../components/CourseMapTabPanel'
import { CourseOutlineSidebar } from '../components/CourseOutlineSidebar'
import { CourseStructurePanel, type StructureScopeSelection } from '../components/CourseStructurePanel'
import { AnswerPanel } from '../components/AnswerPanel'
import { ChunkInspector } from '../components/ChunkInspector'
import { DebugPanel } from '../components/DebugPanel'
import { DocumentUploadPanel } from '../components/DocumentUploadPanel'
import { EmptyCourseState } from '../components/EmptyCourseState'
import { ProgressIndicator } from '../components/ProgressIndicator'
import { QueryForm } from '../components/QueryForm'
import { SidebarViewTabs } from '../components/SidebarViewTabs'
import { SourcesPanel } from '../components/SourcesPanel'
import { TopicsPanel } from '../components/TopicsPanel'
import { TopicFrequencyPanel } from '../components/TopicFrequencyPanel'
import { TrustBadges } from '../components/TrustBadges'
import { useExamStatus } from '../hooks/useExamStatus'
import { useCourseMapEligibility } from '../hooks/useCourseMapEligibility'
import { useSidebarTab } from '../hooks/useSidebarTab'
import { useStudyLayout } from '../hooks/useStudyLayout'
import { TocBrowser } from '../components/TocBrowser'
import { useCourseStructure } from '../hooks/useCourseStructure'
import { useStudyQuery } from '../hooks/useStudyQuery'
import { useStudyTopics } from '../hooks/useStudyTopics'
import { useTopicFrequency } from '../hooks/useTopicFrequency'
import {
  formatCourseMapPromoteError,
  formatCourseMapRebuildError,
  promoteCourseMap,
  rebuildCourseMapOutline,
} from '../api/courseMapClient'
import { normalizeFlexSidebarViews } from '../api/studyLayoutClient'
import { patchStructureMode, StudyTopicsApiError } from '../api/studyTopicsClient'
import { DEFAULT_QUERY_PRESET, isStudyPreset } from '../constants/queryPresets'
import type {
  DocumentUploadResponse,
  GoldenMissHint,
  QueryPreset,
  QueryRequest,
  SidebarViews,
  UploadPanelPhase,
} from '../types'
import '../App.css'
import '../wave4a-theme.css'

const DEFAULT_SIDEBAR_VIEWS: SidebarViews = {
  sources: false,
  topics: false,
  course_map: false,
  course_structure: false,
}

const EMPTY_STRUCTURE_SCOPE: StructureScopeSelection = {
  unitIds: new Set(),
  partIds: new Set(),
  subtopicIds: new Set(),
}

function collectStructureScopeIds(structure: {
  units: Array<{
    id: string
    parts?: Array<{ id: string; subtopics: Array<{ id: string }> }>
    subtopics?: Array<{ id: string }>
  }>
}) {
  const unitIds: string[] = []
  const partIds: string[] = []
  const subtopicIds: string[] = []

  for (const unit of structure.units) {
    unitIds.push(unit.id)
    if (unit.parts?.length) {
      for (const part of unit.parts) {
        partIds.push(part.id)
        for (const subtopic of part.subtopics) {
          subtopicIds.push(subtopic.id)
        }
      }
    } else {
      for (const subtopic of unit.subtopics ?? []) {
        subtopicIds.push(subtopic.id)
      }
    }
  }

  return { unitIds, partIds, subtopicIds }
}

function isPplFixtureCourse(courseId: string, sidebarViews: SidebarViews | undefined): boolean {
  if (courseId.trim().toUpperCase() === 'PPL') return true
  if (!sidebarViews) return false
  return !sidebarViews.sources && !sidebarViews.topics && sidebarViews.course_map
}

export function StudyWorkspacePage() {
  const { courseId: routeCourseId } = useParams<{ courseId: string }>()
  const navigate = useNavigate()
  const activeCourseId = routeCourseId ?? ''

  const handleCourseIdCommit = useCallback(
    (newId: string) => {
      const trimmed = newId.trim()
      if (!trimmed || trimmed === activeCourseId.trim()) return
      navigate(`/courses/${encodeURIComponent(trimmed)}`)
    },
    [activeCourseId, navigate],
  )
  const [question, setQuestion] = useState('')
  const [queryPreset, setQueryPreset] = useState<QueryPreset>(DEFAULT_QUERY_PRESET)
  const [debugEnabled, setDebugEnabled] = useState(false)
  const [selectedHint, setSelectedHint] = useState<GoldenMissHint | null>(null)
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState(0)
  const [outlineConfirmToken, setOutlineConfirmToken] = useState(0)
  const [uploadIndexing, setUploadIndexing] = useState(false)
  const [courseHasDocuments, setCourseHasDocuments] = useState<boolean | null>(null)
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(() => new Set())
  const [selectedTopicIds, setSelectedTopicIds] = useState<Set<string>>(() => new Set())
  const [structureScope, setStructureScope] = useState<StructureScopeSelection>(
    () => EMPTY_STRUCTURE_SCOPE,
  )
  const [organizingTopics, setOrganizingTopics] = useState(false)
  const [organizeError, setOrganizeError] = useState<string | null>(null)
  const [promotingCourseMap, setPromotingCourseMap] = useState(false)
  const [promoteCourseMapError, setPromoteCourseMapError] = useState<string | null>(null)
  const [rebuildingOutline, setRebuildingOutline] = useState(false)
  const [rebuildOutlineError, setRebuildOutlineError] = useState<string | null>(null)
  const prevCourseIdRef = useRef(activeCourseId)
  const prevLayoutSourceIdsRef = useRef<string[]>([])
  const prevTopicIdsRef = useRef<string[]>([])
  const prevStructureScopeRef = useRef<{ unitIds: string[]; partIds: string[]; subtopicIds: string[] }>({
    unitIds: [],
    partIds: [],
    subtopicIds: [],
  })

  const { examIndexReady, data: examStatus } = useExamStatus(activeCourseId, refreshToken)
  const {
    data: studyLayout,
    loading: studyLayoutLoading,
    error: studyLayoutError,
    reload: reloadStudyLayout,
  } = useStudyLayout(activeCourseId, refreshToken)

  const structureMode = studyLayout?.structure_mode ?? 'corpus'
  const outlineAvailable = studyLayout?.outline_available ?? false
  const isPplFixture = isPplFixtureCourse(activeCourseId, studyLayout?.sidebar_views)

  const sidebarViews = useMemo(() => {
    const base = studyLayout?.sidebar_views ?? DEFAULT_SIDEBAR_VIEWS
    return normalizeFlexSidebarViews(base, isPplFixture)
  }, [isPplFixture, studyLayout?.sidebar_views])

  const showFlexSidebar = useMemo(() => {
    if (isPplFixture) return false
    return sidebarViews.sources || sidebarViews.course_structure
  }, [isPplFixture, sidebarViews])

  const { activeTab, setActiveTab } = useSidebarTab(activeCourseId, sidebarViews)

  const showCourseStructureTab = Boolean(sidebarViews.course_structure)
  const {
    data: courseStructure,
    loading: courseStructureLoading,
    error: courseStructureError,
    reload: reloadCourseStructure,
  } = useCourseStructure(
    activeCourseId,
    refreshToken,
    Boolean(showFlexSidebar && showCourseStructureTab),
  )

  const showTopicsTab = sidebarViews.topics
  const {
    topics: studyTopics,
    loading: studyTopicsLoading,
    error: studyTopicsError,
    reload: reloadStudyTopics,
  } = useStudyTopics(activeCourseId, refreshToken, showFlexSidebar && showTopicsTab)

  const {
    data: courseMapEligibility,
    loading: courseMapLoading,
    error: courseMapError,
    reload: reloadCourseMapEligibility,
  } = useCourseMapEligibility(activeCourseId, refreshToken, showFlexSidebar && sidebarViews.course_map)

  const { data: topicFrequencyData } = useTopicFrequency(activeCourseId, refreshToken)

  const examTopicChips = useMemo(() => {
    if (!topicFrequencyData?.units.length) return undefined
    const sorted = [...topicFrequencyData.units].sort((a, b) => b.count - a.count)
    return sorted.slice(0, 2).map((unit) => `Questions on ${unit.title} in past exam papers`)
  }, [topicFrequencyData])

  const { stage, elapsedMs, result, error, streamNotice, submit } = useStudyQuery()
  const loading = stage === 'retrieving' || stage === 'generating'
  const isStreaming = stage === 'generating'

  useEffect(() => {
    setCourseHasDocuments(null)
    setSelectedSourceIds(new Set())
    setSelectedTopicIds(new Set())
    setStructureScope(EMPTY_STRUCTURE_SCOPE)
    prevLayoutSourceIdsRef.current = []
    prevStructureScopeRef.current = { unitIds: [], partIds: [], subtopicIds: [] }
  }, [activeCourseId])

  useEffect(() => {
    if (!showFlexSidebar || !sidebarViews.sources || studyLayoutLoading || !studyLayout) return
    if (studyLayout.course_id !== activeCourseId.trim()) return

    const readyIds = studyLayout.sources
      .filter((source) => source.status === 'ready')
      .map((source) => source.document_id)
    const currentLayoutIds = studyLayout.sources.map((source) => source.document_id)
    const courseChanged = prevCourseIdRef.current !== activeCourseId
    prevCourseIdRef.current = activeCourseId

    const newLayoutIds = currentLayoutIds.filter(
      (id) => !prevLayoutSourceIdsRef.current.includes(id),
    )
    prevLayoutSourceIdsRef.current = currentLayoutIds

    setSelectedSourceIds((prev) => {
      if (courseChanged || prev.size === 0) {
        return new Set(readyIds)
      }

      const next = new Set<string>()
      for (const id of prev) {
        if (readyIds.includes(id)) next.add(id)
      }
      for (const id of newLayoutIds) {
        if (readyIds.includes(id)) next.add(id)
      }
      return next
    })
  }, [activeCourseId, showFlexSidebar, sidebarViews.sources, studyLayout, studyLayoutLoading])

  useEffect(() => {
    if (
      !showFlexSidebar ||
      !sidebarViews.topics ||
      studyTopicsLoading ||
      studyTopics.length === 0
    ) {
      return
    }
    if (studyLayout?.course_id !== activeCourseId.trim()) return

    const topicIds = studyTopics.map((topic) => topic.id)
    const courseChanged = prevCourseIdRef.current !== activeCourseId
    prevCourseIdRef.current = activeCourseId
    const newTopicIds = topicIds.filter((id) => !prevTopicIdsRef.current.includes(id))
    prevTopicIdsRef.current = topicIds

    setSelectedTopicIds((prev) => {
      if (courseChanged || prev.size === 0) {
        return new Set(topicIds)
      }

      const next = new Set<string>()
      for (const id of prev) {
        if (topicIds.includes(id)) next.add(id)
      }
      for (const id of newTopicIds) {
        next.add(id)
      }
      return next
    })
  }, [
    activeCourseId,
    showFlexSidebar,
    sidebarViews.topics,
    studyLayout,
    studyTopics,
    studyTopicsLoading,
  ])

  useEffect(() => {
    if (
      !showFlexSidebar ||
      !showCourseStructureTab ||
      courseStructureLoading ||
      !courseStructure ||
      courseStructure.units.length === 0
    ) {
      return
    }
    if (studyLayout?.course_id !== activeCourseId.trim()) return

    const ids = collectStructureScopeIds(courseStructure)
    const courseChanged = prevCourseIdRef.current !== activeCourseId
    prevCourseIdRef.current = activeCourseId

    const newUnitIds = ids.unitIds.filter((id) => !prevStructureScopeRef.current.unitIds.includes(id))
    const newPartIds = ids.partIds.filter((id) => !prevStructureScopeRef.current.partIds.includes(id))
    const newSubtopicIds = ids.subtopicIds.filter(
      (id) => !prevStructureScopeRef.current.subtopicIds.includes(id),
    )
    prevStructureScopeRef.current = ids

    setStructureScope((prev) => {
      const empty =
        prev.unitIds.size === 0 && prev.partIds.size === 0 && prev.subtopicIds.size === 0

      if (courseChanged || empty) {
        return {
          unitIds: new Set(ids.unitIds),
          partIds: new Set(ids.partIds),
          subtopicIds: new Set(ids.subtopicIds),
        }
      }

      const next: StructureScopeSelection = {
        unitIds: new Set<string>(),
        partIds: new Set<string>(),
        subtopicIds: new Set<string>(),
      }

      for (const id of prev.unitIds) {
        if (ids.unitIds.includes(id)) next.unitIds.add(id)
      }
      for (const id of prev.partIds) {
        if (ids.partIds.includes(id)) next.partIds.add(id)
      }
      for (const id of prev.subtopicIds) {
        if (ids.subtopicIds.includes(id)) next.subtopicIds.add(id)
      }
      for (const id of newUnitIds) next.unitIds.add(id)
      for (const id of newPartIds) next.partIds.add(id)
      for (const id of newSubtopicIds) next.subtopicIds.add(id)

      return next
    })
  }, [
    activeCourseId,
    courseStructure,
    courseStructureLoading,
    showCourseStructureTab,
    showFlexSidebar,
    studyLayout?.course_id,
  ])

  useEffect(() => {
    if (studyLayoutLoading || !showFlexSidebar) return
    const hasDocs = (studyLayout?.sources.length ?? 0) > 0
    const hasStructure = (courseStructure?.units.length ?? 0) > 0
    const hasTopics = studyTopics.length > 0
    setCourseHasDocuments(hasDocs || outlineAvailable || hasStructure || hasTopics)
  }, [
    courseStructure?.units.length,
    outlineAvailable,
    showFlexSidebar,
    studyLayout?.sources.length,
    studyLayoutLoading,
    studyTopics.length,
  ])

  const handlePplOutlineState = useCallback(
    (state: { loaded: boolean; notFound: boolean; hasData: boolean }) => {
      if (!state.loaded || !isPplFixture) return
      setCourseHasDocuments(state.hasData)
    },
    [isPplFixture],
  )

  const handleFlexStructureState = useCallback(
    (state: { hasStructure: boolean }) => {
      if (!showFlexSidebar || activeTab !== 'course_structure') return
      if (state.hasStructure) setCourseHasDocuments(true)
    },
    [activeTab, showFlexSidebar],
  )

  const handleUploadSuccess = (response: DocumentUploadResponse) => {
    const newCourseId = response.course_id.trim()
    if (newCourseId !== activeCourseId.trim()) {
      navigate(`/courses/${encodeURIComponent(newCourseId)}`)
    }
    setCourseHasDocuments(true)
    setRefreshToken((token) => token + 1)
    setOutlineConfirmToken((token) => token + 1)
  }

  const handleUploadPhaseChange = (phase: UploadPanelPhase) => {
    setUploadIndexing(phase === 'indexing')
  }

  const handleOrganizeByTopics = () => {
    const trimmed = activeCourseId.trim()
    if (!trimmed) return

    setOrganizingTopics(true)
    setOrganizeError(null)
    void patchStructureMode(trimmed, 'organized')
      .then(() => {
        setRefreshToken((token) => token + 1)
        setActiveTab('course_structure')
      })
      .catch((err) => {
        if (err instanceof StudyTopicsApiError) {
          setOrganizeError(`${err.status}: ${err.message}`)
        } else {
          setOrganizeError(err instanceof Error ? err.message : 'Could not enable organized study')
        }
      })
      .finally(() => {
        setOrganizingTopics(false)
      })
  }

  const handleFlexSidebarReload = () => {
    reloadStudyLayout()
    reloadCourseStructure()
    reloadStudyTopics()
    reloadCourseMapEligibility()
  }

  const handleStructureSaved = () => {
    setRefreshToken((token) => token + 1)
    reloadCourseStructure()
    reloadStudyLayout()
    handleFlexStructureState({ hasStructure: true })
  }

  const handlePromoteCourseMap = () => {
    const trimmed = activeCourseId.trim()
    if (!trimmed) return

    setPromotingCourseMap(true)
    setPromoteCourseMapError(null)
    void promoteCourseMap(trimmed)
      .then(() => {
        setRefreshToken((token) => token + 1)
        setOutlineConfirmToken((token) => token + 1)
      })
      .catch((err) => {
        setPromoteCourseMapError(formatCourseMapPromoteError(err))
      })
      .finally(() => {
        setPromotingCourseMap(false)
      })
  }

  const handleRebuildOutline = () => {
    const trimmed = activeCourseId.trim()
    if (!trimmed) return

    setRebuildingOutline(true)
    setRebuildOutlineError(null)
    void rebuildCourseMapOutline(trimmed)
      .then(() => {
        setRefreshToken((token) => token + 1)
        setOutlineConfirmToken((token) => token + 1)
      })
      .catch((err) => {
        setRebuildOutlineError(formatCourseMapRebuildError(err))
      })
      .finally(() => {
        setRebuildingOutline(false)
      })
  }

  const readySourceIds = useMemo(() => {
    if (!studyLayout) return []
    return studyLayout.sources
      .filter((source) => source.status === 'ready')
      .map((source) => source.document_id)
  }, [studyLayout])

  const readyTopicIds = useMemo(
    () => studyTopics.map((topic) => topic.id),
    [studyTopics],
  )

  const selectedReadyTopicIds = useMemo(
    () => readyTopicIds.filter((id) => selectedTopicIds.has(id)),
    [readyTopicIds, selectedTopicIds],
  )

  const selectedReadySourceIds = useMemo(
    () => readySourceIds.filter((id) => selectedSourceIds.has(id)),
    [readySourceIds, selectedSourceIds],
  )

  const allStructureIds = useMemo(
    () => (courseStructure ? collectStructureScopeIds(courseStructure) : null),
    [courseStructure],
  )

  const selectedStructureUnitIds = useMemo(
    () => (allStructureIds?.unitIds ?? []).filter((id) => structureScope.unitIds.has(id)),
    [allStructureIds, structureScope.unitIds],
  )

  const selectedStructurePartIds = useMemo(
    () => (allStructureIds?.partIds ?? []).filter((id) => structureScope.partIds.has(id)),
    [allStructureIds, structureScope.partIds],
  )

  const selectedStructureSubtopicIds = useMemo(
    () => (allStructureIds?.subtopicIds ?? []).filter((id) => structureScope.subtopicIds.has(id)),
    [allStructureIds, structureScope.subtopicIds],
  )

  const sourceSelectionActive = showFlexSidebar && activeTab === 'sources'
  const topicSelectionActive = showFlexSidebar && activeTab === 'topics'
  const structureSelectionActive = showFlexSidebar && activeTab === 'course_structure'

  const corpusSourceSelectionBlocked =
    sourceSelectionActive && readySourceIds.length > 0 && selectedReadySourceIds.length === 0

  const organizedTopicSelectionBlocked =
    topicSelectionActive &&
    isStudyPreset(queryPreset) &&
    readyTopicIds.length > 0 &&
    selectedReadyTopicIds.length === 0

  const hasStructureNodes =
    (allStructureIds?.unitIds.length ?? 0) +
      (allStructureIds?.partIds.length ?? 0) +
      (allStructureIds?.subtopicIds.length ?? 0) >
    0

  const structureScopeSelected =
    selectedStructureUnitIds.length +
      selectedStructurePartIds.length +
      selectedStructureSubtopicIds.length >
    0

  const structureSelectionBlocked =
    structureSelectionActive &&
    isStudyPreset(queryPreset) &&
    hasStructureNodes &&
    !structureScopeSelected

  const submitBlocked =
    corpusSourceSelectionBlocked || organizedTopicSelectionBlocked || structureSelectionBlocked
  const submitBlockedMessage = corpusSourceSelectionBlocked
    ? 'Select at least one source'
    : organizedTopicSelectionBlocked
      ? 'Select at least one topic'
      : structureSelectionBlocked
        ? 'Select at least one unit, part, or subtopic'
        : null

  const handleSubmit = () => {
    if (submitBlocked) return

    setSelectedChunkId(null)

    const body: QueryRequest = {
      course_id: activeCourseId.trim(),
      question: question.trim(),
      preset: queryPreset,
      debug: debugEnabled,
    }

    if (
      sourceSelectionActive &&
      selectedReadySourceIds.length > 0 &&
      selectedReadySourceIds.length < readySourceIds.length
    ) {
      body.source_ids = selectedReadySourceIds
    } else if (
      structureSelectionActive &&
      isStudyPreset(queryPreset) &&
      structureScopeSelected &&
      allStructureIds
    ) {
      const allUnitsSelected =
        allStructureIds.unitIds.length > 0 &&
        selectedStructureUnitIds.length === allStructureIds.unitIds.length
      const allPartsSelected =
        allStructureIds.partIds.length > 0 &&
        selectedStructurePartIds.length === allStructureIds.partIds.length
      const allSubtopicsSelected =
        allStructureIds.subtopicIds.length > 0 &&
        selectedStructureSubtopicIds.length === allStructureIds.subtopicIds.length
      const fullStructureSelected =
        allStructureIds.unitIds.length === selectedStructureUnitIds.length &&
        allStructureIds.partIds.length === selectedStructurePartIds.length &&
        allStructureIds.subtopicIds.length === selectedStructureSubtopicIds.length

      if (!fullStructureSelected) {
        if (selectedStructureUnitIds.length > 0 && !allUnitsSelected) {
          body.unit_ids = selectedStructureUnitIds
        }
        if (selectedStructurePartIds.length > 0 && !allPartsSelected) {
          body.part_ids = selectedStructurePartIds
        }
        if (selectedStructureSubtopicIds.length > 0 && !allSubtopicsSelected) {
          body.subtopic_ids = selectedStructureSubtopicIds
        }
      }
    } else if (
      topicSelectionActive &&
      isStudyPreset(queryPreset) &&
      selectedReadyTopicIds.length > 0 &&
      selectedReadyTopicIds.length < readyTopicIds.length
    ) {
      body.topic_ids = selectedReadyTopicIds
    }

    void submit(body, { useStream: !debugEnabled })
  }

  const showEmptyState =
    !debugEnabled && courseHasDocuments === false && !loading && !result && !uploadIndexing

  return (
    <div className="app-shell">
      <div className="ambient-streaks" aria-hidden="true" />
      <div className="app">
        <header className="app-header reveal-on-load">
          <div className="app-header-main">
            <Link to="/courses" className="courses-back-link">
              ← All courses
            </Link>
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
          queryPreset={queryPreset}
        />

        <main className="app-main reveal-on-load reveal-delay-1">
          <div className="column column-primary">
            {!debugEnabled && (
              <DocumentUploadPanel
                courseId={activeCourseId}
                disabled={loading}
                onCourseIdCommit={handleCourseIdCommit}
                onUploadSuccess={handleUploadSuccess}
                onPhaseChange={handleUploadPhaseChange}
              />
            )}

            {showEmptyState && <EmptyCourseState />}

            <QueryForm
              courseId={activeCourseId}
              question={question}
              preset={queryPreset}
              debugEnabled={debugEnabled}
              loading={loading || uploadIndexing}
              examIndexReady={examIndexReady}
              examTopicChips={examTopicChips}
              submitBlocked={submitBlocked}
              submitBlockedMessage={submitBlockedMessage}
              onCourseIdCommit={handleCourseIdCommit}
              onQuestionChange={setQuestion}
              onPresetChange={setQueryPreset}
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

            {result && (
              <AnswerPanel
                result={result}
                queryPreset={queryPreset}
                examIndexReady={examIndexReady}
                debugEnabled={debugEnabled}
                isStreaming={isStreaming}
              />
            )}
          </div>

          <div className="column column-secondary">
            {isPplFixture && (
              <>
                <CourseOutlineSidebar
                  courseId={activeCourseId}
                  refreshToken={refreshToken}
                  outlineConfirmToken={outlineConfirmToken}
                  onSectionSelect={setQuestion}
                  onOutlineState={handlePplOutlineState}
                />

                <TopicFrequencyPanel
                  courseId={activeCourseId}
                  refreshToken={refreshToken}
                  queryPreset={queryPreset}
                  heatmapSource={examStatus?.heatmap_source}
                  onSelectExamPreset={() => setQueryPreset('exam')}
                />
              </>
            )}

            {showFlexSidebar && (
              <div className="flex-sidebar-shell">
                <SidebarViewTabs
                  sidebarViews={sidebarViews}
                  activeTab={activeTab}
                  onTabChange={setActiveTab}
                />

                {activeTab === 'sources' && sidebarViews.sources && (
                  <SourcesPanel
                    courseId={activeCourseId}
                    layout={studyLayout}
                    loading={studyLayoutLoading}
                    error={studyLayoutError}
                    selectedSourceIds={selectedSourceIds}
                    onSelectedSourceIdsChange={setSelectedSourceIds}
                    onReload={reloadStudyLayout}
                    onOrganizeByTopics={handleOrganizeByTopics}
                    organizing={organizingTopics}
                    organizeError={organizeError}
                  />
                )}

                {activeTab === 'course_structure' && sidebarViews.course_structure && (
                  <CourseStructurePanel
                    courseId={activeCourseId}
                    layout={studyLayout}
                    layoutLoading={studyLayoutLoading}
                    layoutError={studyLayoutError}
                    structure={courseStructure}
                    structureLoading={courseStructureLoading}
                    structureError={courseStructureError}
                    queryPreset={queryPreset}
                    scopeSelection={structureScope}
                    onScopeSelectionChange={setStructureScope}
                    onQueryPresetChange={setQueryPreset}
                    onReload={handleFlexSidebarReload}
                    onStructureSaved={handleStructureSaved}
                  />
                )}

                {activeTab === 'topics' && sidebarViews.topics && (
                  <TopicsPanel
                    courseId={activeCourseId}
                    layout={studyLayout}
                    layoutLoading={studyLayoutLoading}
                    layoutError={studyLayoutError}
                    topics={studyTopics}
                    topicsLoading={studyTopicsLoading}
                    topicsError={studyTopicsError}
                    queryPreset={queryPreset}
                    selectedTopicIds={selectedTopicIds}
                    onSelectedTopicIdsChange={setSelectedTopicIds}
                    onReload={handleFlexSidebarReload}
                  />
                )}

                {activeTab === 'course_map' && sidebarViews.course_map && isPplFixture && (
                  <CourseMapTabPanel
                    courseId={activeCourseId}
                    structureMode={structureMode}
                    outlineAvailable={outlineAvailable}
                    refreshToken={refreshToken}
                    outlineConfirmToken={outlineConfirmToken}
                    queryPreset={queryPreset}
                    heatmapSource={examStatus?.heatmap_source}
                    onSectionSelect={setQuestion}
                    onSelectExamPreset={() => setQueryPreset('exam')}
                    eligibility={courseMapEligibility}
                    eligibilityLoading={courseMapLoading}
                    eligibilityError={courseMapError}
                    promoting={promotingCourseMap}
                    promoteError={promoteCourseMapError}
                    onPromote={handlePromoteCourseMap}
                    onReloadEligibility={reloadCourseMapEligibility}
                    rebuilding={rebuildingOutline}
                    rebuildError={rebuildOutlineError}
                    onRebuildOutline={handleRebuildOutline}
                  />
                )}
              </div>
            )}

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
