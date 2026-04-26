import { useState } from 'react';
import './App.css';

const App = () => {
  const [reportText, setReportText] = useState('');
  const [returnedSummary, setReturnedSummary] = useState(null);

  const onAnalyze = async () => {
    const response = await fetch("http://127.0.0.1:8000/analyze_report", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        report_text: reportText,
      }),
    });

    const data = await response.json();
    setReturnedSummary(data);
  };

  const fileData = () => {
    if (returnedSummary) {
      return (
<div>
  <h2>{returnedSummary.brief_title}</h2>

  <p><strong>Risk:</strong> {returnedSummary.risk_label}</p>
  <p>{returnedSummary.summary}</p>

  <h3>Rationale</h3>
  <ul>
    {returnedSummary.risk_rationale?.map((item, i) => (
      <li key={i}>{item}</li>
    ))}
  </ul>

  <h3>Recommended Actions</h3>
  <ul>
    {returnedSummary.recommended_next_steps?.map((item, i) => (
      <li key={i}>{item}</li>
    ))}
  </ul>

<h3>Historical Comparisons</h3>
<ul>
  {returnedSummary.historical_comparisons?.map((item, i) => (
    <li key={i}>{typeof item === "string" ? item : item.summary || item.title}</li>
  ))}
</ul>

<h3>Policy Context</h3>
<ul>
  {returnedSummary.policy_context?.map((item, i) => (
    <li key={i}>{typeof item === "string" ? item : item.summary || item.title}</li>
  ))}
</ul>

  <h3>Uncertainty</h3>
  <ul>
    {returnedSummary.uncertainty_flags?.map((item, i) => (
      <li key={i}>{item}</li>
    ))}
  </ul>
</div>
      );
    }

    return (
      <div>
        <br />
        <h4>Paste an incident report, ProMED alert, WHO item, news article, or field note.</h4>
      </div>
    );
  };

  return (
    <div>
      <h1>BioWatch Brief</h1>
      <h3>Paste a report to receive a rapid response summary</h3>

      <textarea
        rows="10"
        cols="80"
        value={reportText}
        onChange={(e) => setReportText(e.target.value)}
        placeholder="Paste incident report here..."
      />

      <br />

      <button onClick={onAnalyze}>Analyze</button>

      {fileData()}
    </div>
  );
};

export default App;