import axios from "axios";

const Axios = () => {
  return axios.create({
    baseURL: "http://10.194.1.103:8080/",
    method: "post",
    headers: { "Content-type": "application/json" },
    timeout: 5000,
    withCredentials: false,
  });
};

export default Axios;
