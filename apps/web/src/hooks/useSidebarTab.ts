import { useCallback, useEffect, useMemo, useState } from 'react'

import type { SidebarViews, SidebarViewTab } from '../types'

const STORAGE_PREFIX = 'studypilot:sidebar-tab:'

function defaultTabForViews(views: SidebarViews): SidebarViewTab {
  if (views.sources) return 'sources'
  if (views.course_structure) return 'course_structure'
  if (views.topics) return 'topics'
  if (views.course_map) return 'course_map'
  return 'course_structure'
}

function visibleTabsForViews(views: SidebarViews): SidebarViewTab[] {
  const tabs: SidebarViewTab[] = []
  if (views.sources) tabs.push('sources')
  if (views.course_structure) tabs.push('course_structure')
  if (views.topics) tabs.push('topics')
  if (views.course_map) tabs.push('course_map')
  return tabs
}

interface UseSidebarTabResult {
  activeTab: SidebarViewTab
  setActiveTab: (tab: SidebarViewTab) => void
  visibleTabs: SidebarViewTab[]
}

export function useSidebarTab(courseId: string, sidebarViews: SidebarViews): UseSidebarTabResult {
  const visibleTabs = useMemo(() => visibleTabsForViews(sidebarViews), [sidebarViews])
  const [activeTab, setActiveTabState] = useState<SidebarViewTab>(() =>
    defaultTabForViews(sidebarViews),
  )

  useEffect(() => {
    const trimmed = courseId.trim()
    if (!trimmed) return

    const stored = localStorage.getItem(`${STORAGE_PREFIX}${trimmed}`) as SidebarViewTab | null
    const fallback = defaultTabForViews(sidebarViews)
    const next =
      stored && visibleTabs.includes(stored)
        ? stored
        : visibleTabs.includes(fallback)
          ? fallback
          : (visibleTabs[0] ?? 'course_structure')
    setActiveTabState(next)
  }, [courseId, sidebarViews, visibleTabs])

  const setActiveTab = useCallback(
    (tab: SidebarViewTab) => {
      setActiveTabState(tab)
      const trimmed = courseId.trim()
      if (trimmed) {
        localStorage.setItem(`${STORAGE_PREFIX}${trimmed}`, tab)
      }
    },
    [courseId],
  )

  return { activeTab, setActiveTab, visibleTabs }
}
