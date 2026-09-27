import React, { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Line, Points } from "@react-three/drei";


export default function NeuralGraph(){

const group = useRef();


const particles = useMemo(()=>{

let data=[];

for(let i=0;i<260;i++){

let t=i/260*Math.PI*6;

let radius=1.8 + Math.sin(t*3)*0.5;

data.push([
Math.cos(t)*radius,
Math.sin(t*2)*0.8,
Math.sin(t)*radius
]);

}

return data;


},[]);



useFrame(({clock})=>{

if(group.current){

group.current.rotation.y =
clock.elapsedTime*0.15;

group.current.rotation.z =
Math.sin(clock.elapsedTime*.2)*.1;

}

});



return (

<group ref={group}>


<Points
positions={particles.flat()}
>

<pointsMaterial

color="#ffffff"

size={0.015}

transparent

opacity={0.8}

/>

</Points>



{
particles.slice(0,80).map((p,i)=>(

<Line

key={i}

points={[
p,
particles[(i+15)%particles.length]
]}

color="#1f4b50"

transparent

opacity={0.35}

/>

))

}



<mesh>


<icosahedronGeometry
args={[0.5,5]}
/>


<meshStandardMaterial

color="#0b2025"

wireframe

emissive="#2dd4c5"

emissiveIntensity={3}

/>


</mesh>



</group>

)

}