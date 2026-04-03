import { useEffect } from 'react'

export const PROFILE_CHANGED = 'pyedi:profile-changed'

interface ProfileChangedDetail {
  action: 'created' | 'deleted' | 'updated'
  profileName: string
}

export function emitProfileChanged(detail: ProfileChangedDetail): void {
  window.dispatchEvent(new CustomEvent(PROFILE_CHANGED, { detail }))
}

export function useProfileChanged(callback: (detail: ProfileChangedDetail) => void): void {
  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<ProfileChangedDetail>
      callback(ce.detail)
    }
    window.addEventListener(PROFILE_CHANGED, handler)
    return () => window.removeEventListener(PROFILE_CHANGED, handler)
  }, [callback])
}
