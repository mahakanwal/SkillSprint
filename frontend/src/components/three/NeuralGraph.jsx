import React, { useMemo, useRef } from "react";
import { Points, Line } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";


export default function NeuralGraph() {

  const group = useRef();


  const nodes = useMemo(() => {

    const arr = [];

    for(let i=0;i<180;i++){

      const r = 2 + Math.random()*1.5;
      const a = Math.random()*Math.PI*2;

      arr.push([
        Math.cos(a)*r,
        (Math.random()-0.5)*3,
        Math.sin(a)*r
      ]);

    }

    return arr;

  },[]);



  useFrame(({clock})=>{

    if(group.current){

      group.current.rotation.y =
      clock.getElapsedTime()*0.08;

    }

  });



return (

<group ref={group}>


<Points
positions={
nodes.flat()
}
stride={3}
>

<pointsMaterial

color="#2dd4c5"

size={0.025}

transparent

opacity={0.8}

/>

</Points>



{

nodes.slice(0,50).map((p,i)=>(

<Line

key={i}

points={[
p,
nodes[(i+5)%nodes.length]
]}

color="#24535b"

lineWidth={0.5}

transparent

opacity={0.5}

/>

))

}



<mesh>

<icosahedronGeometry
args={[0.7,4]}
/>


<meshStandardMaterial

color="#06272c"

emissive="#2dd4c5"

emissiveIntensity={2}

wireframe

/>

</mesh>



</group>

)

}