import React from 'react';
import { getDecision, getLosses, getPredictiveMaintenance, getRecentEvents, getSummary } from '../services/api.js';

const REFRESH_MS = 7000;
const fallbackLosses = [
  { loss_category: 'breakdown loss', impact: 0 },
  { loss_category: 'performance loss', impact: 0 },
  { loss_category: 'quality loss', impact: 0 },
];

export function useOperationsData(filters) {
  const [summaryData, setSummaryData] = React.useState(null);
  const [decisionData, setDecisionData] = React.useState(null);
  const [losses, setLosses] = React.useState(fallbackLosses);
  const [predictiveData, setPredictiveData] = React.useState([]);
  const [events, setEvents] = React.useState([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState('');

  const loadData = React.useCallback(async () => {
    try {
      const [summary, decision, nextLosses, predictive, recentEvents] = await Promise.all([
        getSummary(filters),
        getDecision(filters),
        getLosses(filters),
        getPredictiveMaintenance(filters),
        getRecentEvents(),
      ]);

      setSummaryData((current) => (isObject(summary) ? summary : current));
      setDecisionData((current) => (isObject(decision) ? decision : current));
      setLosses(Array.isArray(nextLosses) && nextLosses.length ? nextLosses : fallbackLosses);
      setPredictiveData(Array.isArray(predictive) ? predictive : []);
      setEvents(Array.isArray(recentEvents) ? recentEvents : []);
      setError('');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Data refresh failed');
    } finally {
      setIsLoading(false);
    }
  }, [filters]);

  React.useEffect(() => {
    loadData();
    const interval = window.setInterval(loadData, REFRESH_MS);
    return () => window.clearInterval(interval);
  }, [loadData]);

  return { summaryData, decisionData, losses, predictiveData, events, isLoading, error, refreshData: loadData };
}

function isObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value);
}
