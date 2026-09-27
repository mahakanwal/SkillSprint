import axios from "axios";


const API_URL = "http://localhost:8000";


export const revalidatePlan = async (planId) => {

    try {

        const response = await axios.post(
            `${API_URL}/validation/revalidate/${planId}`
        );


        return response.data;


    } catch (error) {

        console.error(
            "Validation error:",
            error
        );


        throw error;

    }

};