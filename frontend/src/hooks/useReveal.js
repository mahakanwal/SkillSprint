import { useEffect } from "react";

import gsap from "gsap";

import {
ScrollTrigger
}
from "gsap/ScrollTrigger";


gsap.registerPlugin(
ScrollTrigger
);



export default function useReveal(){


useEffect(()=>{


const items =
document.querySelectorAll(
".reveal"
);



items.forEach((item)=>{


gsap.fromTo(

item,


{

opacity:0,

y:80,

filter:"blur(20px)"

},


{

opacity:1,

y:0,

filter:"blur(0px)",


duration:1,


ease:"power3.out",


scrollTrigger:{

trigger:item,

start:"top 85%",

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