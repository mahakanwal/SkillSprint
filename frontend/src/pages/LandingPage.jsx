import React from "react";
import { Canvas } from "@react-three/fiber";
import { Float, OrbitControls, Stars } from "@react-three/drei";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Brain,
  FileText,
  ShieldCheck,
  Sparkles,
  Target,
  LogIn
} from "lucide-react";

import "./LandingPage.css";


function AIOrb(){

  return (
    <Float
      speed={2}
      rotationIntensity={1}
      floatIntensity={1}
    >

      <mesh>

        <icosahedronGeometry args={[1.4,5]} />

        <meshStandardMaterial
          color="#2dd4c5"
          emissive="#0e8f91"
          emissiveIntensity={2}
          wireframe
        />

      </mesh>

    </Float>
  );
}



export default function LandingPage(){


return (

<div className="ss-page">


{/* HERO */}

<section className="hero">


<div className="hero-bg">
<Canvas camera={{position:[0,0,5]}}>

<ambientLight intensity={1}/>

<pointLight
position={[3,3,3]}
color="#2dd4c5"
/>

<AIOrb/>

<Stars
radius={100}
depth={50}
count={3000}
factor={4}
/>


<OrbitControls
enableZoom={false}
/>


</Canvas>
</div>



<motion.div
className="hero-content"
initial={{opacity:0,y:40}}
animate={{opacity:1,y:0}}
>


<div className="badge">
<Sparkles size={15}/>
 Generative AI Powered
</div>


<h1>

Transform Employee
<br/>

<span>
Onboarding With AI
</span>

</h1>


<p>

SkillSprint AI analyzes company documents,
policies, SOPs and role requirements to create
personalized learning journeys.

</p>


<div className="buttons">


<a href="/try" className="primary">

Try SkillSprint AI
<ArrowRight size={18}/>

</a>


<a href="/login" className="secondary">

<LogIn size={18}/>
Login

</a>


</div>


</motion.div>


</section>





{/* HOW IT WORKS */}


<section className="section">


<div className="section-title">

<h2>
How SkillSprint AI Works
</h2>

<p>
From documents to personalized employee training.
</p>

</div>



<div className="cards">


<Card
icon={<FileText/>}
title="Upload Documents"
text="Analyze policies, SOPs, FAQs and company knowledge."
/>


<Card
icon={<Brain/>}
title="AI Generation"
text="Generate learning modules, tasks, quizzes and assessments."
/>


<Card
icon={<Target/>}
title="Role Based Learning"
text="Create onboarding plans based on employee role."
/>


<Card
icon={<ShieldCheck/>}
title="Validation"
text="Verify requirements using independent validation."
/>


</div>


</section>







{/* AI EXPERIENCE */}



<section className="ai-section">


<div>


<h2>

Personalized Learning Experience

</h2>


<p>

Every employee receives a customized onboarding path
based on department, role, experience and business rules.

</p>


<ul>

<li>Learning Modules</li>
<li>Practical Tasks</li>
<li>Quizzes</li>
<li>Progress Tracking</li>

</ul>


</div>



<div className="dashboard">


<div>
Module Completion
<strong>86%</strong>
</div>


<div>
Requirement Coverage
<strong>100%</strong>
</div>


<div>
Validation Status
<strong>Verified</strong>
</div>


</div>



</section>








{/* VALIDATION */}



<section className="validation">


<ShieldCheck size={60}/>


<h2>

Reliable AI With Ground Truth Validation

</h2>


<p>

SkillSprint AI combines Generative AI with
Python based validation to check coverage,
traceability and unsupported content.

</p>



<div className="pipeline">


<span>AI Generation</span>

↓

<span>Python Validation</span>

↓

<span>Verified Plan</span>


</div>


</section>







{/* CTA */}



<section className="cta">


<h2>

Build Smarter Employee Training
With SkillSprint AI

</h2>


<div>


<a href="/try">
Start Now
</a>


<a href="/login">
Login
</a>


</div>


</section>



</div>

)

}





function Card({icon,title,text}){


return (

<motion.div

whileHover={{
y:-10
}}

className="card"

>


<div className="icon">

{icon}

</div>


<h3>

{title}

</h3>


<p>

{text}

</p>


</motion.div>

)

}