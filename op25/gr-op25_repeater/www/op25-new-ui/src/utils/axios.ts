import axios from "axios";

const Axios = () => {
  return axios.create({
    baseURL: "/",
    method: "post",
    headers: { "Content-type": "application/json" },
    timeout: 5000,
    withCredentials: false,
  });
};

export default Axios;
