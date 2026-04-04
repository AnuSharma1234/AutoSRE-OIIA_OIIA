'use client';
import { useQuery } from '@tanstack/react-query';
import { getIncidents, getIncident } from '@/lib/api';
import type { GetIncidentsParams } from '@/lib/types';

export function useIncidents(params?: GetIncidentsParams) {
  return useQuery({
    queryKey: ['incidents', params],
    queryFn: () => getIncidents(params),
    refetchInterval: 10_000,
  });
}

export function useIncident(id: string) {
  return useQuery({
    queryKey: ['incident', id],
    queryFn: () => getIncident(id),
    refetchInterval: 5_000,
    enabled: !!id,
  });
}
