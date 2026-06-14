// Single source of truth for all backend endpoint paths.
export const ENDPOINTS = Object.freeze({
  chat: '/chat',
  sessionClose: '/session/close',
  members: '/api/members',
  history: '/api/history',
  onboardingStatus: '/api/onboarding/status',
  onboardingComplete: '/api/onboarding/complete',
  onboardingRoster: '/api/onboarding/roster',
  onboardingMemberData: '/api/onboarding/member-data',
})
