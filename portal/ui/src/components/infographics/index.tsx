import { useMemo } from 'react'
import type React from 'react'
import type { InfographicThemeProps } from './types'
import WhiteboardTheme from './WhiteboardTheme'
import WatercolorTheme from './WatercolorTheme'
import StickyNotesTheme from './StickyNotesTheme'
import RetroArcadeTheme from './RetroArcadeTheme'

export type { InfographicThemeProps } from './types'

const THEMES: React.ComponentType<InfographicThemeProps>[] = [
  WhiteboardTheme,
  WatercolorTheme,
  StickyNotesTheme,
  RetroArcadeTheme,
]

export const THEME_NAMES = ['Whiteboard Sketch', 'Watercolor', 'Sticky Notes & Yarn', 'Retro Arcade'] as const

/**
 * Returns a random infographic theme component, stable for the lifetime of the component.
 */
export function useRandomTheme(): {
  Theme: React.ComponentType<InfographicThemeProps>
  themeName: string
  themeIndex: number
} {
  return useMemo(() => {
    const idx = Math.floor(Math.random() * THEMES.length)
    return {
      Theme: THEMES[idx],
      themeName: THEME_NAMES[idx],
      themeIndex: idx,
    }
  }, [])
}

export { WhiteboardTheme, WatercolorTheme, StickyNotesTheme, RetroArcadeTheme }
