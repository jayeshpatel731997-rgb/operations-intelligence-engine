import React from 'react';
import { ErrorBoundary } from '../components/ErrorBoundary.jsx';
import {
  CriticalIssues,
  DecisionCenter,
  ExecutiveSummary,
  Header,
  LiveOperationsFeed,
  LossAndTrend,
  MachineHealthMatrix,
  PredictiveRiskPanel,
  ScopeControls,
  SimulationStudio,
  StatusBar,
  formatDateTime,
} from '../components/PlatformSections.jsx';
import { useLiveOperations } from '../hooks/useLiveOperations.js';
import { useOperationsData } from '../hooks/useOperationsData.js';
import { useSimulation } from '../hooks/useSimulation.js';
import { SCENARIOS, downloadReport, uploadCsv } from '../services/api.js';

function getScenarioLabel(scenario) {
  return SCENARIOS.find((item) => item.id === scenario)?.label || 'Normal';
}

function DashboardContent() {
  const [plantId, setPlantId] = React.useState('');
  const [lineId, setLineId] = React.useState('');
  const [machineId, setMachineId] = React.useState('');
  const [scenario, setScenario] = React.useState('normal');
  const [uploadStatus, setUploadStatus] = React.useState('');
  const [uploadError, setUploadError] = React.useState('');
  const [useCsvSource, setUseCsvSource] = React.useState(false);
  const [simulationAction, setSimulationAction] = React.useState('reduce downtime');
  const [improvementPercent, setImprovementPercent] = React.useState(20);

  const today = new Date();
  const formatDate = (date) => date.toISOString().split('T')[0];
  const filters = React.useMemo(() => ({
    plantId: plantId || undefined,
    lineId: lineId || undefined,
    machineId: machineId || undefined,
    startDate: formatDate(new Date(Date.now() - 24 * 60 * 60 * 1000)),
    endDate: formatDate(today),
    scenario,
  }), [plantId, lineId, machineId, scenario]);

  const { streamData, oeeHistory, status } = useLiveOperations();
  const {
    summaryData,
    decisionData,
    predictiveData,
    events,
    isLoading,
    error,
    refreshData,
  } = useOperationsData(filters);
  const { result: simulationResult, isRunning, error: simulationError, simulate } = useSimulation(filters);

  const machineMetrics = Array.isArray(summaryData?.machine_metrics) ? summaryData.machine_metrics : [];
  const health = Array.isArray(summaryData?.machine_health) ? summaryData.machine_health : streamData.machine_health;
  const criticalAlerts = Array.isArray(summaryData?.critical_alerts) ? summaryData.critical_alerts : streamData.alerts;
  const lastUpdated = summaryData?.last_updated
    ? formatDateTime(summaryData.last_updated)
    : streamData.timestamp
      ? formatDateTime(streamData.timestamp)
      : 'Waiting for live data';
  const activeMachines = machineId ? 1 : machineMetrics.length || 3;

  const handlePlantChange = (nextPlantId) => {
    setPlantId(nextPlantId);
    setLineId('');
    setMachineId('');
  };

  const handleUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploadStatus('Uploading CSV...');
    setUploadError('');
    try {
      await uploadCsv(file);
      setUseCsvSource(true);
      setUploadStatus('CSV uploaded successfully. Analysis refreshed.');
      await refreshData();
    } catch (uploadIssue) {
      setUploadError(uploadIssue instanceof Error ? uploadIssue.message : 'Upload failed');
      setUploadStatus('');
    } finally {
      event.target.value = '';
    }
  };

  const handleDownload = async (format) => {
    setUploadError('');
    try {
      await downloadReport(filters, format);
    } catch (downloadError) {
      setUploadError(downloadError instanceof Error ? downloadError.message : 'Report download failed');
    }
  };

  const handleSimulation = () => {
    simulate({
      action: simulationAction,
      improvementPercent: Number(improvementPercent),
    });
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-slate-900 p-4 text-white sm:p-6">
      <Header scenarioLabel={getScenarioLabel(scenario)} />

      <StatusBar
        dataSource={useCsvSource ? 'Uploaded CSV' : 'Live Stream'}
        lastUpdated={lastUpdated}
        activeMachines={activeMachines}
        status={status}
        alert={streamData.alert}
      />

      <ScopeControls
        plantId={plantId}
        lineId={lineId}
        machineId={machineId}
        scenario={scenario}
        scopeOptions={summaryData?.scope_options}
        onPlantChange={handlePlantChange}
        onLineChange={setLineId}
        onMachineChange={setMachineId}
        onScenarioChange={setScenario}
        onUpload={handleUpload}
        onDownload={handleDownload}
        uploadStatus={uploadStatus}
        uploadError={uploadError || error}
      />

      <ExecutiveSummary summaryData={summaryData} streamData={streamData} isLoading={isLoading} />
      <CriticalIssues alerts={criticalAlerts} />

      <div className="mb-6 grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <DecisionCenter decisionData={decisionData} />
        <PredictiveRiskPanel predictiveData={predictiveData?.length ? predictiveData : summaryData?.predictive_risk} />
      </div>

      <div className="mb-6 grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <SimulationStudio
          action={simulationAction}
          improvementPercent={improvementPercent}
          setAction={setSimulationAction}
          setImprovementPercent={setImprovementPercent}
          result={simulationResult}
          isRunning={isRunning}
          error={simulationError}
          onRun={handleSimulation}
        />
        <MachineHealthMatrix health={health} machineMetrics={machineMetrics} />
      </div>

      <div className="mb-6 grid gap-6 xl:grid-cols-[1fr_1fr]">
        <LiveOperationsFeed events={events} streamData={streamData} />
        <section className="rounded-lg border border-slate-700 bg-slate-800 p-5 shadow-lg">
          <h2 className="text-xl font-bold">Executive Summary</h2>
          <p className="mt-3 text-sm leading-relaxed text-slate-300">
            {summaryData?.summary_report || 'Live operational summary will appear as soon as the control tower receives data.'}
          </p>
          <p className="mt-4 text-sm text-slate-400">
            Primary root cause: {summaryData?.top_losses?.[0]?.loss_category || 'No dominant loss driver yet.'}
          </p>
        </section>
      </div>

      <LossAndTrend summaryData={summaryData} oeeHistory={oeeHistory} />

      <footer className="mt-10 rounded-lg border border-slate-700 bg-slate-900 p-4 text-xs text-slate-400">
        Powered by FastAPI + React | Simulated Industrial Data | Designed for real-time decision support
      </footer>
    </div>
  );
}

export default function Dashboard() {
  return (
    <ErrorBoundary>
      <DashboardContent />
    </ErrorBoundary>
  );
}
