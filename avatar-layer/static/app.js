(function () {
  "use strict";

  const state = {
    lastResult: null,
    muted: false,
    reducedMotion: false,
    textOnly: false
  };

  const $ = (id) => document.getElementById(id);

  function setAvatarState(next, mode) {
    document.body.dataset.state = next;
    document.querySelector(".shell").dataset.mode = mode || "general";
    $("stateLabel").textContent = next;
    $("statusPill").textContent = next;
  }

  function samplePayload() {
    return {
      role: "viewer",
      assessment_mode: "dpp",
      product_id: "THB-AVATAR-001",
      agent_ids: ["expert-dpp-readiness", "compliance-cybersecurity"],
      reduced_motion: state.reducedMotion,
      text_only: state.textOnly,
      muted: state.muted,
      assessment: {
        readiness: { status: "review_required", score: 68 },
        findings: [
          {
            agent_id: "expert-dpp-readiness",
            agent_version: "0.1.0",
            severity: "medium",
            status: "needs_review",
            missing_evidence: ["Data Matrix durability test", "public DPP URL"],
            recommended_action: "Validate Data Matrix placement and attach the public DPP URL before release.",
            traceability: {
              evidence_refs: [
                {
                  type: "product_master_record",
                  reference: "product-layer/THB-AVATAR-001",
                  classification: "internal",
                  confidence: "verified"
                }
              ]
            }
          },
          {
            agent_id: "compliance-cybersecurity",
            agent_version: "0.1.0",
            severity: "high",
            status: "needs_review",
            missing_evidence: ["SBOM approval"],
            recommended_action: "Route cybersecurity findings to a human reviewer.",
            restricted_evidence_refs: [
              {
                type: "vulnerability_details",
                reference: "security/CVE-internal-001",
                classification: "restricted",
                text: "Restricted exploit detail intentionally present to verify speech redaction."
              }
            ]
          }
        ]
      }
    };
  }

  async function runAssessment() {
    setAvatarState("thinking", "dpp");
    const response = await fetch("/api/avatar/assess", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(samplePayload())
    });
    if (!response.ok) {
      setAvatarState("error", "general");
      throw new Error("Assessment request failed: " + response.status);
    }
    const result = await response.json();
    state.lastResult = result;
    renderResult(result);
    speak(result.spoken_summary);
  }

  function renderResult(result) {
    const mode = result.assessment_mode || "general";
    const stateName = result.severity === "critical" || result.severity === "high" ? "warning" : "speaking";
    setAvatarState(stateName, mode);
    $("assessmentStatus").textContent = (result.assessment_status || "unknown").replaceAll("_", " ");
    $("severity").textContent = result.severity || "none";
    $("confidence").textContent = Math.round((result.confidence || 0) * 100) + "%";
    $("displaySummary").textContent = result.display_summary || "";
    $("productId").textContent = result.product_id || "none";
    $("hiddenRefs").textContent = String(result.restricted_refs_hidden || 0) + " hidden";
    $("sessionMeta").textContent = result.session ? result.session.session_id : "no session";
    $("missingEvidence").textContent = (result.missing_evidence || []).join(", ") || "none";
    $("agentVersions").textContent = Object.entries(result.agent_versions || {})
      .map(([id, version]) => id + " " + version)
      .join(", ") || "none";

    const transcript = $("transcriptEntries");
    transcript.replaceChildren();
    for (const entry of (result.transcript && result.transcript.entries) || []) {
      const li = document.createElement("li");
      li.textContent = entry.text;
      transcript.appendChild(li);
    }

    const refs = $("evidenceRefs");
    refs.replaceChildren();
    for (const ref of result.evidence_refs || []) {
      const li = document.createElement("li");
      const label = ref.redacted ? "redacted" : ref.classification || "internal";
      li.textContent = ref.type + " | " + ref.reference + " | " + label;
      refs.appendChild(li);
    }
  }

  function speak(text) {
    if (state.muted || state.textOnly || !("speechSynthesis" in window)) {
      setAvatarState("idle", state.lastResult ? state.lastResult.assessment_mode : "general");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 0.95;
    utterance.pitch = 0.95;
    utterance.onstart = () => setAvatarState("speaking", state.lastResult ? state.lastResult.assessment_mode : "general");
    utterance.onend = () => setAvatarState("idle", state.lastResult ? state.lastResult.assessment_mode : "general");
    window.speechSynthesis.speak(utterance);
  }

  $("runSample").addEventListener("click", () => {
    runAssessment().catch((error) => {
      $("displaySummary").textContent = error.message;
    });
  });

  $("replaySpeech").addEventListener("click", () => {
    if (state.lastResult) {
      speak(state.lastResult.spoken_summary);
    }
  });

  $("stopSpeech").addEventListener("click", () => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setAvatarState("idle", state.lastResult ? state.lastResult.assessment_mode : "general");
  });

  $("muteToggle").addEventListener("change", (event) => {
    state.muted = event.target.checked;
    if (state.muted && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  });

  $("motionToggle").addEventListener("change", (event) => {
    state.reducedMotion = event.target.checked;
    document.body.classList.toggle("reduced-motion", state.reducedMotion);
  });

  $("textOnlyToggle").addEventListener("change", (event) => {
    state.textOnly = event.target.checked;
    document.body.classList.toggle("text-only", state.textOnly);
    if (state.textOnly && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  });
})();
