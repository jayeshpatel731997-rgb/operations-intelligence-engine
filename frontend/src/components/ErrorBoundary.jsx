import React from 'react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-950 p-6 text-white">
          <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-5">
            <h1 className="text-xl font-semibold">Control tower temporarily unavailable</h1>
            <p className="mt-2 text-sm text-red-100">The last known data is protected. Refresh the page to reconnect.</p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
