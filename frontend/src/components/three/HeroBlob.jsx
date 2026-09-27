import React from "react";
import blobImage from "../../assets/hero-blob.png";

export default function HeroBlob() {
  return (
    <div className="hero-blob-wrap">

      <img
        src={blobImage}
        alt="SkillSprint AI"
        className="hero-blob-img"
        draggable="false"
      />

      <div className="float-card document-card">
        <span>SOURCE</span>
        Company Policy.pdf
      </div>

      <div className="float-card ai-card">
        <span>AI GENERATED</span>
        Learning Plan
      </div>

      <div className="float-card verify-card">
        <span>STATUS</span>
        ✓ Verified
      </div>

    </div>
  );
}