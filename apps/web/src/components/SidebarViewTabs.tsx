import type { SidebarViews, SidebarViewTab } from '../types'

const TAB_LABELS: Record<SidebarViewTab, string> = {
  sources: 'Sources',
  course_structure: 'Course structure',
  topics: 'Topics',
  course_map: 'Course map',
}

interface SidebarViewTabsProps {
  sidebarViews: SidebarViews
  activeTab: SidebarViewTab
  onTabChange: (tab: SidebarViewTab) => void
}

function isTabVisible(views: SidebarViews, tab: SidebarViewTab): boolean {
  if (tab === 'course_structure') return Boolean(views.course_structure)
  return views[tab]
}

export function SidebarViewTabs({ sidebarViews, activeTab, onTabChange }: SidebarViewTabsProps) {
  const tabs = (Object.keys(TAB_LABELS) as SidebarViewTab[]).filter((key) =>
    isTabVisible(sidebarViews, key),
  )

  if (tabs.length <= 1) return null

  return (
    <div className="preset-tabs sidebar-panel-tabs" role="tablist" aria-label="Sidebar view">
      {tabs.map((tab) => (
        <button
          key={tab}
          type="button"
          role="tab"
          aria-selected={activeTab === tab}
          className={['preset-tab', activeTab === tab ? 'is-active' : ''].filter(Boolean).join(' ')}
          onClick={() => onTabChange(tab)}
        >
          {TAB_LABELS[tab]}
        </button>
      ))}
    </div>
  )
}
