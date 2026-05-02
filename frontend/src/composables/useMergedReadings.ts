import type { UtilityReading, Room } from '@/types'

export interface MergedReading {
  room_id: number
  reading_date: string
  water_reading?: UtilityReading
  electricity_reading?: UtilityReading
  monthly_rent?: number
  payment_cycle?: number
  lease_start?: string
  total_amount: number
  notes: string
  is_paid?: boolean
}

export function mergeReadings(readings: UtilityReading[], roomOptions: Room[]): MergedReading[] {
  const map = new Map<string, MergedReading>()

  readings.forEach(reading => {
    const key = `${reading.room_id}_${reading.reading_date}`

    if (!map.has(key)) {
      const room = roomOptions.find(r => r.id === reading.room_id)
      map.set(key, {
        room_id: reading.room_id,
        reading_date: reading.reading_date,
        water_reading: reading.utility_type === 'water' ? reading : undefined,
        electricity_reading: reading.utility_type === 'electricity' ? reading : undefined,
        monthly_rent: room?.monthly_rent,
        payment_cycle: room?.payment_cycle,
        total_amount: 0,
        notes: '',
      })
    } else {
      const merged = map.get(key)!
      if (reading.utility_type === 'water') {
        merged.water_reading = reading
      } else if (reading.utility_type === 'electricity') {
        merged.electricity_reading = reading
      }
    }
  })

  Array.from(map.values()).forEach(merged => {
    const cycle = Math.max(1, merged.payment_cycle || 1)
    let total = (merged.monthly_rent || 0) * cycle

    if (merged.water_reading) {
      total += merged.water_reading.amount || 0
    }
    if (merged.electricity_reading) {
      total += merged.electricity_reading.amount || 0
    }

    merged.total_amount = total
    merged.notes = merged.water_reading?.notes || merged.electricity_reading?.notes || ''
    merged.is_paid = !!(
      (merged.water_reading && merged.water_reading.payment_id) ||
      (merged.electricity_reading && merged.electricity_reading.payment_id)
    )
  })

  return Array.from(map.values()).sort((a, b) =>
    new Date(b.reading_date).getTime() - new Date(a.reading_date).getTime()
  )
}
