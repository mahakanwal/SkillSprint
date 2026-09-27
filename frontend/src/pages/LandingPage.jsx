import React from "react";

import {
Canvas
} from "@react-three/fiber";

import {
Stars,
OrbitControls
} from "@react-three/drei";


import {
motion
} from "framer-motion";


import {
Link
} from "react-router-dom";


import {
ArrowRight
} from "lucide-react";


import NeuralGraph from "../components/three/NeuralGraph";


import "./LandingPage.css";




export default function LandingPage(){


return (

<div className="landing">


<nav className="nav">


<div className="logo">

<div className="logo-mark">
✦
</div>

SkillSprint
<span>
AI
</span>

</div>



<div className="links">

<a>Product</a>
<a>Features</a>
<a>Validation</a>
<a>About</a>

</div>



<div className="nav-buttons">

<Link to="/login">
Login
</Link>


<Link
className="nav-cta"
to="/login"
>

Try Now

</Link>


</div>


</nav>





<section className="hero">


<div className="hero-copy">


<motion.span

initial={{opacity:0}}

animate={{opacity:1}}

>

GENERATIVE AI POWERED

</motion.span>




<h1>

Turn company
<br/>

knowledge into
<br/>

<span>

intelligent onboarding

</span>

</h1>



<p>

SkillSprint AI analyzes policies,
SOPs, role documents and creates
personalized employee learning journeys.

</p>



<div className="hero-actions">


<Link
to="/login"
className="primary"
>

Start Building

<ArrowRight/>

</Link>


<Link
to="/login"
className="outline"
>

Login

</Link>


</div>



</div>





<div className="webgl">


<Canvas>

<ambientLight intensity={1}/>

<pointLight
position={[3,3,3]}
color="#2dd4c5"
/>


<NeuralGraph/>


<Stars
count={3000}
radius={30}
/>


<OrbitControls
enableZoom={false}
/>


</Canvas>


</div>


</section>







<section className="steps">


<div>

<h3>
01. Upload
</h3>

<p>
Company policies, SOPs,
FAQs and role documents.
</p>

</div>



<div>

<h3>
02. Generate
</h3>

<p>
AI creates personalized
learning modules and tasks.
</p>

</div>




<div>

<h3>
03. Validate
</h3>

<p>
Python validates coverage,
sources and accuracy.
</p>

</div>



</section>







<section className="big-section">


<h2>

Your onboarding,
finally intelligent

</h2>


<div className="graph-box">

<div>
Employee Profile
</div>

<div>
AI Learning Plan
</div>

<div>
Validation Result
</div>


</div>


</section>






<section className="cta">


<h2>

Build smarter learning
experiences.

</h2>


<Link to="/login">

Get Started

</Link>


</section>



</div>


)

}