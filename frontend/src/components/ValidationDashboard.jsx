import React, { useEffect, useState } from "react";

import {
    revalidatePlan
} from "../services/validationService";


import "./ValidationDashboard.css";



export default function ValidationDashboard({
    planId
}) {


    const [validation, setValidation] = useState(null);

    const [loading, setLoading] = useState(false);

    const [error, setError] = useState("");




    const loadValidation = async () => {


        try {


            setLoading(true);

            setError("");



            const result = await revalidatePlan(
                planId
            );


            setValidation(
                result.data
            );



        } catch (err) {


            setError(
                "Validation failed"
            );


        } finally {


            setLoading(false);


        }

    };



    useEffect(() => {


        if(planId){

            loadValidation();

        }


    }, [planId]);




    if(loading){

        return (
            <div>
                Running validation...
            </div>
        );

    }



    if(error){

        return (
            <div className="error">
                {error}
            </div>
        );

    }




    if(!validation){

        return null;

    }




    return (

        <div className="validation-wrapper">


            <div className="validation-top">


                <h2>
                    AI Validation Report
                </h2>


                <button
                    onClick={loadValidation}
                >

                    Re Validate

                </button>


            </div>




            <div className="score-grid">


                <ScoreCard

                    title="Overall"

                    score={
                        validation.overall_score
                    }

                />



                <ScoreCard

                    title="Coverage"

                    score={
                        validation.coverage.score
                    }

                />



                <ScoreCard

                    title="Traceability"

                    score={
                        validation.traceability.score
                    }

                />



                <ScoreCard

                    title="Consistency"

                    score={
                        validation.consistency.score
                    }

                />


            </div>



            <div className="status-box">

                Status:

                <strong>

                    {
                        validation.validation_status
                    }

                </strong>


            </div>



        </div>

    );

}




function ScoreCard({
    title,
    score
}) {


    return (

        <div className="score-card">


            <h3>
                {title}
            </h3>


            <span>
                {score}%
            </span>


            <div className="bar">

                <div

                    style={{
                        width:`${score}%`
                    }}

                />

            </div>


        </div>

    );


}