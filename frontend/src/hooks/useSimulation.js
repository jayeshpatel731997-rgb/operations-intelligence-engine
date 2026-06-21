import React from 'react';
import { runSimulation } from '../services/api.js';

export function useSimulation(filters) {
  const [result, setResult] = React.useState(null);
  const [isRunning, setIsRunning] = React.useState(false);
  const [error, setError] = React.useState('');

  const simulate = React.useCallback(async ({ action, improvementPercent }) => {
    setIsRunning(true);
    setError('');
    try {
      const payload = {
        machine_id: filters.machineId || undefined,
        plant_id: filters.plantId || undefined,
        line_id: filters.lineId || undefined,
        action,
        improvement_percent: improvementPercent,
      };
      const nextResult = await runSimulation(payload);
      setResult(nextResult);
      return nextResult;
    } catch (simulateError) {
      setError(simulateError instanceof Error ? simulateError.message : 'Simulation failed');
      return null;
    } finally {
      setIsRunning(false);
    }
  }, [filters]);

  return { result, isRunning, error, simulate };
}
