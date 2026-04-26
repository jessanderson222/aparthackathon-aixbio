import { useState } from 'react';
import axios from "axios";
import './App.css';
import data from './summary.json'
const summary = data.summary;

const App = () => {
  const [selectedFile, setSelectedFile] = useState(null);
	const onFileChange = (event) => {
		setSelectedFile(event.target.files[0]);
	};

  // update to accomodate what comes back from the api
  const [returnedSummary, setReturnedSummary] = useState('');

  //TODO: When the API is ready, use a useEffect to make the API call when the value of selectedFile updates.
  // then, use that file to send to the API.


  // update this once we have the API in place
	const onFileUpload = (setReturnedSummary) => {
		const formData = new FormData();
		formData.append(
			"myFile",
			selectedFile,
			selectedFile.name
		);
		console.log(selectedFile);

    // when we need to contact the API
		// axios.post("api/uploadfile", formData);

    //currently using a dummy data file but we can update
    setReturnedSummary(summary);
    console.log(returnedSummary)
	};

	const fileData = () => {
    if (returnedSummary) {
      // TODO: this is where we will return all the info that we want a user to see.
      // I followed the data structure from the comments in Slack but can update.
      // Rendering will follow this pattern though where we have an HTML element for each
      // specific JSON element.
      return (
        <h1>{returnedSummary?.policy_context?.id}</h1>
      )
    } else if (selectedFile) {
      return (
        <div>
          <h2>File Details:</h2>
          <p>File Name: {selectedFile.name}</p>
          <p>File Type: {selectedFile.type}</p>
          <p>
            Last Modified: {selectedFile.lastModifiedDate.toDateString()}
          </p>
        </div>
        );
    } else {
      return (
        <div>
          <br />
          <h4>An incident report could include a ProMED alert, WHO Disease Outbreak News item, news article, or field note.</h4>
          <h4>File must be a PDF.</h4>
        </div>
      );
    }
	};

	return (
		<div>
			<h1>BioWatch Brief</h1>
			<h3>Please upload a file to receive a rapid response summary</h3>
			<div>
				<input type="file" accept="application/pdf" onChange={onFileChange} />
				<button onClick={() => onFileUpload(setReturnedSummary)}>Upload!</button>
			</div>
			{fileData()}
		</div>
	);
}

export default App;
