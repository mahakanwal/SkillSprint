import React from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  FileText,
  Brain,
  ShieldCheck,
  Sparkles,
  Cpu                     
} from "lucide-react";

import HeroGalaxy from "../components/three/HeroGalaxy";       // ✅ sirf hero galaxy
import HeroBlob from "../components/three/HeroBlob";           // ✅ blob + tool image
import Sprinkles from "../components/three/Sprinkles";         // ✅ validation section sprinkles
import useReveal from "../hooks/useReveal";
import "./LandingPage.css";


export default function LandingPage(){

useReveal();

return (

<div className="ss-landing">


{/* NAVBAR */}

<nav className="ss-nav">


<Link to="/" className="ss-logo">

  <div className="ss-logo-icon">
    <Cpu size={18} />
  </div>

  <div className="ss-logo-text">
    <span className="ss-logo-title">
      SkillSprint <b>AI</b>
    </span>
  
  </div>

</Link>



<div className="ss-nav-links">

<a href="#process">
Process
</a>

<a href="#ai">
AI Engine
</a>

<a href="#validation">
Validation
</a>

<a href="#features">
Features
</a>


</div>



<div className="ss-nav-actions">

<Link
to="/login"
className="login-btn"
>
Login
</Link>


<Link
to="/login"
className="try-btn"
>
Try Now
</Link>


</div>


</nav>







{/* HERO */}

<section className="ss-hero">

  {/* Sprinkles — validation section jaisa */}
  <div className="hero-bg">
    <Sprinkles count={110} radius={140} />
  </div>

  <div className="ss-hero-content reveal">

    <div className="ss-badge">
      <Sparkles size={14}/>
      GENERATIVE AI POWERED
    </div>

    <h1>
      Transform company
      <br/>
      knowledge into
      <br/>
      <span>
        intelligent onboarding
      </span>
    </h1>

    <p>
      SkillSprint AI analyzes company
      documents, policies, SOPs and
      role requirements to create
      personalized employee learning
      experiences.
    </p>

    <div className="ss-actions">

      <Link to="/login" className="main-btn">
        Start Building
        <ArrowRight size={18}/>
      </Link>

      <Link to="/login" className="border-btn">
        Login
      </Link>

    </div>

  </div>

  {/* Right side — blob with human + 3 floating cards */}
  <div className="ss-hero-visual">
    <HeroBlob />
  </div>

</section>









{/* PROCESS SECTION */}



<section
id="process"
className="ss-process reveal"
>


<div className="section-heading">


<p>
HOW IT WORKS
</p>


<h2>

From documents
to intelligent learning

</h2>


</div>




<div className="process-grid">


<div className="process-item">


<FileText/>


<h3>
01. Upload
</h3>


<p>

Upload policies,
SOPs, FAQs and
company documents.

</p>


</div>





<div className="process-item">


<Brain/>


<h3>
02. Generate
</h3>


<p>

AI creates role based
learning modules,
tasks and assessments.

</p>


</div>







<div className="process-item">


<ShieldCheck/>


<h3>
03. Validate
</h3>


<p>

Python validation checks
requirements,
sources and accuracy.

</p>


</div>



</div>


</section>









{/* AI EXPERIENCE */}



<section
id="ai"
className="ss-ai-section reveal"
>


<div className="ai-copy">


<p>
PERSONALIZED LEARNING
</p>


<h2>

Every employee gets
a smarter learning path

</h2>



<span>

Based on role, department,
experience level and company
requirements.

</span>



<div className="tags">


<div>
Learning Modules
</div>


<div>
Practical Tasks
</div>


<div>
Quizzes
</div>


<div>
Progress Tracking
</div>



</div>


</div>





<div className="ai-dashboard">


<div>

Employee Profile

<strong>
Finance Officer
</strong>

</div>


<div>

Generated Plan

<strong>
90 Day Journey
</strong>

</div>


<div>

Coverage

<strong>
100% Verified
</strong>

</div>



</div>



</section>









{/* VALIDATION */}

<section
id="validation"
className="validation-section reveal"
>

  <div className="validation-bg">
    <Sprinkles count={90} radius={150} />
  </div>

  <div className="validation-content">

    <div className="validation-core">

      <ShieldCheck size={70}/>

    </div>



    <h2>

      Generative AI
      <br/>

      +
      <br/>

      Python Validation

    </h2>



    <p>

      Ensure every generated learning plan
      is traceable, complete and aligned
      with company requirements.

    </p>



    <div className="validation-list">


      <span>
        Requirement Coverage
      </span>


      <span>
        Source Traceability
      </span>


      <span>
        Conflict Detection
      </span>


      <span>
        Quality Verification
      </span>


    </div>

  </div>

</section>









{/* CTA */}

<section className="ss-final reveal">

  <h2>
    Build the future of
    employee onboarding.
  </h2>

  <p>
    SkillSprint AI turns company knowledge
    into actionable learning experiences.
  </p>

  <Link to="/login">
    Get Started
    <ArrowRight size={18}/>
  </Link>

</section>

{/* FOOTER */}

<footer className="ss-footer">

  <div className="ss-footer-inner">

    <div className="ss-footer-left">

<div className="ss-footer-logo">

  <div className="ss-logo-icon">
    <Cpu size={16} />
  </div>

  <div className="ss-logo-text">
    <span className="ss-logo-title">
      SkillSprint <b>AI</b>
    </span>
  </div>

</div>

      <p className="ss-footer-tag">
        Generative AI powered onboarding.
      </p>

    </div>

    <div className="ss-footer-links">

      <a href="#process">Process</a>
      <a href="#ai">AI Engine</a>
      <a href="#validation">Validation</a>
      <a href="#features">Features</a>

    </div>

    <div className="ss-footer-right">
      <span>© {new Date().getFullYear()} SkillSprint AI</span>
    </div>

  </div>

</footer>

</div>

);


}





