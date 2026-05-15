const { google } = require('googleapis')
const __userRepository = require('../repositories/userRepository')
const { getAuthenticatedOAuth2Client } = require('./googleAuth')

// In-memory per-user cache. Keyed by `${userId}:${daysAhead}`. Cleared on TTL expiry.
// 60s is short enough that newly-scheduled meetings appear within a minute,
// long enough that rapid page loads (dashboard + nav) hit the cache.
const CACHE_TTL_MS = 60 * 1000
const _cache = new Map()

const cacheKey = (userId, daysAhead) => `${userId}:${daysAhead}`

const cacheGet = (key) => {
  const hit = _cache.get(key)
  if (!hit) return null
  if (Date.now() > hit.expiresAt) { _cache.delete(key); return null }
  return hit.data
}

const cacheSet = (key, data) => {
  _cache.set(key, { data, expiresAt: Date.now() + CACHE_TTL_MS })
}

class CalendarService {
  async getCalendarEvents(userId, daysAhead = 1) {
    const ck = cacheKey(userId, daysAhead)
    const cached = cacheGet(ck)
    if (cached) return cached
    // Get user from database
    const user = await __userRepository.getUserById(userId)
    if (!user || !user.google_token) {
      throw new Error('User not authenticated with Google')
    }

    // Get authenticated OAuth2 client with automatic refresh
    const oauth2Client = await getAuthenticatedOAuth2Client(user)

    // Initialize calendar API
    const calendar = google.calendar({ version: 'v3', auth: oauth2Client })

    // Calculate time range (now to daysAhead days from now)
    const now = new Date()
    const endTime = new Date(now.getTime() + daysAhead * 24 * 60 * 60 * 1000)

    // Fetch events
    const response = await calendar.events.list({
      calendarId: 'primary',
      timeMin: now.toISOString(),
      timeMax: endTime.toISOString(),
      maxResults: 50,
      singleEvents: true,
      orderBy: 'startTime'
    })

    const events = response.data.items || []

    const mapped = events.map(event => ({
      google_event_id: event.id,
      title: event.summary,
      description: event.description,
      start_time: event.start.dateTime || event.start.date,
      end_time: event.end.dateTime || event.end.date,
      location: event.location,
      attendees: event.attendees,
      meeting_link: event.hangoutLink,
      html_link: event.htmlLink,
      is_all_day: !event.start.dateTime
    }))
    cacheSet(ck, mapped)
    return mapped
  }

  // Returns ALL events for today in IST (00:00 to 23:59) — past, ongoing, and upcoming.
  async getEventsForToday(userId) {
    const ck = `today_full:${userId}`
    const cached = cacheGet(ck)
    if (cached) return cached

    const user = await __userRepository.getUserById(userId)
    if (!user || !user.google_token) {
      throw new Error('User not authenticated with Google')
    }
    const oauth2Client = await getAuthenticatedOAuth2Client(user)
    const calendar = google.calendar({ version: 'v3', auth: oauth2Client })

    // Compute IST start/end of today using a fixed offset string.
    const istDateStr = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' })
    const dayStart = new Date(`${istDateStr}T00:00:00+05:30`)
    const dayEnd = new Date(`${istDateStr}T23:59:59.999+05:30`)

    const response = await calendar.events.list({
      calendarId: 'primary',
      timeMin: dayStart.toISOString(),
      timeMax: dayEnd.toISOString(),
      maxResults: 100,
      singleEvents: true,
      orderBy: 'startTime'
    })

    const events = response.data.items || []
    const mapped = events.map(event => ({
      google_event_id: event.id,
      title: event.summary,
      description: event.description,
      start_time: event.start.dateTime || event.start.date,
      end_time: event.end.dateTime || event.end.date,
      location: event.location,
      attendees: event.attendees,
      meeting_link: event.hangoutLink,
      html_link: event.htmlLink,
      is_all_day: !event.start.dateTime
    }))
    cacheSet(ck, mapped)
    return mapped
  }

  async getTodayMeetingsSchema(userId) {
    const events = await this.getCalendarEvents(userId, 1)

    if (events.length === 0) {
      return []
    }

    return events.map(event => ({
      component: 'MeetingItem',
      props: {
        time: event.is_all_day
          ? 'All Day'
          : new Date(event.start_time).toLocaleTimeString('en-IN', {
              hour: '2-digit',
              minute: '2-digit',
              hour12: true,
              timeZone: 'Asia/Kolkata'
            }),
        title: event.title || 'Untitled',
        desc: event.description || '',
        location: event.location || null,
        meetingLink: event.meeting_link || null,
        calendarLink: event.html_link || null
      }
    }))
  }
}

module.exports = new CalendarService()
