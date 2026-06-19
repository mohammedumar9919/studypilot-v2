type SidebarPanelTab = 'primary' | 'course-map'

interface SidebarPanelTabsProps {
  primaryLabel: string
  activeTab: SidebarPanelTab
  courseMapDisabled?: boolean
  showCourseMapTab: boolean
  onTabChange: (tab: SidebarPanelTab) => void
}

export function SidebarPanelTabs({
  primaryLabel,
  activeTab,
  courseMapDisabled = false,
  showCourseMapTab,
  onTabChange,
}: SidebarPanelTabsProps) {
  if (!showCourseMapTab) return null

  return (
    <div className="preset-tabs sidebar-panel-tabs" role="tablist" aria-label="Sidebar view">
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === 'primary'}
        className={['preset-tab', activeTab === 'primary' ? 'is-active' : ''].filter(Boolean).join(' ')}
        onClick={() => onTabChange('primary')}
      >
        {primaryLabel}
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === 'course-map'}
        className={['preset-tab', activeTab === 'course-map' ? 'is-active' : '']
          .filter(Boolean)
          .join(' ')}
        disabled={courseMapDisabled}
        title={courseMapDisabled ? 'Course Map unlocks after promotion' : undefined}
        onClick={() => onTabChange('course-map')}
      >
        Course map
      </button>
    </div>
  )
}

export type { SidebarPanelTab }
