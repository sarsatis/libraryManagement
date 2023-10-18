function menuRedirect(data){

		 if(data == "bookList" ){
			
			window.location = "bookList.html";
		}
		else if(data == "ReturnBook" ){
			
			window.location = "returnBook.html";
		}
		else if(data == "member" ){
			
			window.location = "member.html";
		}else{
			
			window.location = "mainContent.html";
		}
			

			


}




function returnbook(){
	var category=document.getElementById("search").value
	/*var searchValue=document.getElementById("search").value*/

	if(category == "none"){
	alert("please select the category");
	return 0;
	}
	/*if(searchValue == ""){
	alert("please fill in search box");
	return 0;
	}*/

	if(category == "return"){
		
		getBookId(searchValue);
		
	}



	}
