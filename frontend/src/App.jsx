import React from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate
} from "react-router-dom";

import {
  AuthProvider,
  useAuth
} from "./context/AuthContext";


import LandingPage from "./pages/LandingPage";

import { LoginPage } from "./components/auth/LoginPage";


import { AdminDashboard } 
from "./components/dashboard/AdminDashboard";

import { ReviewerDashboard }
from "./components/dashboard/ReviewerDashboard";

import { ManagerDashboard }
from "./components/dashboard/ManagerDashboard";

import { EmployeeDashboard }
from "./components/dashboard/EmployeeDashboard";


import { Loader2 } from "lucide-react";



function ProtectedDashboard(){

const {
isAuthenticated,
isLoading,
role,
logout
}=useAuth();



if(isLoading){

return (

<div className="flex min-h-dvh items-center justify-center">

<Loader2
size={22}
className="animate-spin"
/>

</div>

)

}



if(!isAuthenticated){

return <Navigate to="/login"/>

}



switch(role){


case "admin":

return (
<AdminDashboard
onLogout={logout}
viewerRole="admin"
/>
)



case "training_manager":

return (
<AdminDashboard
onLogout={logout}
viewerRole="training_manager"
/>
)



case "reviewer":

return (
<ReviewerDashboard
onLogout={logout}
/>
)



case "manager":

return (
<ManagerDashboard
onLogout={logout}
/>
)



case "employee":

return (
<EmployeeDashboard
onLogout={logout}
/>
)



default:

return <Navigate to="/login"/>


}



}




function LoginRoute(){


const {
isAuthenticated
}=useAuth();


if(isAuthenticated){

return <Navigate to="/dashboard"/>

}


return <LoginPage/>;


}





export default function App(){


return (

<AuthProvider>


<BrowserRouter>


<Routes>


{/* Landing Page */}

<Route

path="/"

element={<LandingPage/>}

/>



{/* Login */}

<Route

path="/login"

element={<LoginRoute/>}

/>



{/* Dashboard */}

<Route

path="/dashboard"

element={<ProtectedDashboard/>}

/>



</Routes>


</BrowserRouter>


</AuthProvider>

)


}