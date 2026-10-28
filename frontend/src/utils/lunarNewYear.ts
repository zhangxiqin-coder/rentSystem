// 农历春节（正月初一）对应公历日期表（2025–2045）
// 春节日期由月相决定，没有简单公式，采用查表法（日期依据天文年历核对）
const CNY_DATES: Array<{ year: number; date: string }> = [
  { year: 2025, date: '2025-01-29' },
  { year: 2026, date: '2026-02-17' },
  { year: 2027, date: '2027-02-06' },
  { year: 2028, date: '2028-01-26' },
  { year: 2029, date: '2029-02-13' },
  { year: 2030, date: '2030-02-03' },
  { year: 2031, date: '2031-01-23' },
  { year: 2032, date: '2032-02-11' },
  { year: 2033, date: '2033-01-31' },
  { year: 2034, date: '2034-02-19' },
  { year: 2035, date: '2035-02-08' },
  { year: 2036, date: '2036-01-28' },
  { year: 2037, date: '2037-02-15' },
  { year: 2038, date: '2038-02-04' },
  { year: 2039, date: '2039-01-24' },
  { year: 2040, date: '2040-02-12' },
  { year: 2041, date: '2041-02-01' },
  { year: 2042, date: '2042-01-22' },
  { year: 2043, date: '2043-02-10' },
  { year: 2044, date: '2044-01-30' },
  { year: 2045, date: '2045-02-17' }
]

export interface NextCnyInfo {
  year: number     // 农历年份
  date: string     // 公历日期 YYYY-MM-DD
  daysLeft: number // 距今天数（0 = 就是今天）
}

// 获取下一个农历春节（含今天）：返回日期和剩余天数，表外返回 null
export function getNextLunarNewYear(now: Date = new Date()): NextCnyInfo | null {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  for (const item of CNY_DATES) {
    const [y, m, d] = item.date.split('-').map(Number)
    const cny = new Date(y, m - 1, d)
    const daysLeft = Math.round((cny.getTime() - today.getTime()) / 86400000)
    if (daysLeft >= 0) {
      return { ...item, daysLeft }
    }
  }
  return null
}
