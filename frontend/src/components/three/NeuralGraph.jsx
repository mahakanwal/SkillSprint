import React, { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Points, PointMaterial, Line } from "@react-three/drei";


export default function NeuralGraph(){

const group = useRef();


const points = useMemo(()=>{

const arr=[];

for(let i=0;i<250;i++){

const angle =
Math.random()*Math.PI*2;


const radius =
1.2 + Math.random()*2;


arr.push([

Math.cos(angle)*radius,

(Math.random()-0.5)*2.5,

Math.sin(angle)*radius

]);

}


return arr;


},[]);





useFrame(({clock})=>{


if(group.current){

group.current.rotation.y =
clock.elapsedTime * .12;


group.current.rotation.x =
Math.sin(clock.elapsedTime*.3)*.15;


}


});



return (

<group ref={group}>


{/* PARTICLES */}

<Points
positions={points.flat()}
>

<PointMaterial

transparent

color="#2dd4c5"

size={0.018}

sizeAttenuation

depthWrite={false}

/>

</Points>





{/* CONNECTION NETWORK */}


{
points.slice(0,80).map((point,index)=>(


<Line

key={index}

points={[
point,
points[(index+7)%points.length]
]}

color="#174047"

transparent

opacity={0.45}

lineWidth={0.4}

/>


))

}





{/* AI CORE */}


<mesh>


<icosahedronGeometry
args={[
0.55,
5
]}
/>


<meshStandardMaterial

color="#07191d"

wireframe

emissive="#2dd4c5"

emissiveIntensity={3}

/>


</mesh>




{/* INNER GLOW */}


<mesh>


<sphereGeometry
args={[
0.25,
32,
32
]}
/>


<meshStandardMaterial

color="#2dd4c5"

emissive="#2dd4c5"

emissiveIntensity={5}

/>


</mesh>



</group>


)

}