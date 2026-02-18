/**
 * Hook for fetching available skills from the system
 */

import { useState, useEffect } from 'react';
import { getSkills } from '../api/client';
import type { Skill } from '../types';

export interface UseSkillsResult {
  skills: Skill[];
  isLoading: boolean;
  error: string | null;
}

export function useSkills(): UseSkillsResult {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSkills()
      .then(setSkills)
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load skills');
      })
      .finally(() => setIsLoading(false));
  }, []);

  return { skills, isLoading, error };
}
