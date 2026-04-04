'use client';
import { useQuery } from '@tanstack/react-query';
import { getClusterOverview } from '@/lib/api';

export function useClusterOverview() {
  return useQuery({
    queryKey: ['cluster', 'overview'],
    queryFn: getClusterOverview,
    refetchInterval: 10_000,
  });
}
