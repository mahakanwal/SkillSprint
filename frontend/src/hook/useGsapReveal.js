import { useEffect } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";


gsap.registerPlugin(ScrollTrigger);


export default function useGsapReveal(){


useEffect(()=>{


const elements =
document.querySelectorAll(
".reveal"
);



elements.forEach((el)=>{


gsap.fromTo(
el,

{
opacity:0,
y:80,
filter:"blur(15px)"
},

{

opacity:1,
y:0,
filter:"blur(0px)",

duration:1.2,

ease:"power3.out",

scrollTrigger:{
trigger:el,
start:"top 80%",
toggleActions:
"play none none reverse"
}

}

);


});



return ()=>{

ScrollTrigger.killAll();

};


},[]);



}