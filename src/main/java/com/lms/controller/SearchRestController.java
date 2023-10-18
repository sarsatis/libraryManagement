package com.lms.controller;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.Date;
import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.util.ObjectUtils;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.bind.annotation.RestController;

import com.lms.model.Books;
import com.lms.model.Member;
import com.lms.service.BookSearch;

/**
 * @author nitrawat
 *
 */
@RestController
public class SearchRestController{

	@Autowired
	private BookSearch bookSearch;
	

	/**
	 * @param searchValue
	 * @return List of InputSearch
	 */
	@RequestMapping(value ="/getData/{searchValue}", method = RequestMethod.GET, produces = MediaType.APPLICATION_JSON_VALUE)
	@ResponseBody
	public List<String> getData(@PathVariable String searchValue){
		
		int searchValue1=Integer.parseInt(searchValue);
		List inputList = new ArrayList();
		Books input = bookSearch.getInputSearch(searchValue);
		if(!ObjectUtils.isEmpty(input)){
			inputList.add(input.getAuthor());
			inputList.add(input.getAvailable());
			inputList.add(input.getTitle());
			inputList.add(input.getBookid());
		}
		
		return inputList;
	}
	
	@RequestMapping(value ="/name/{searchValue}", method = RequestMethod.GET, produces = MediaType.APPLICATION_JSON_VALUE)
	@ResponseBody
	public List<String> getDataByname(@PathVariable String searchValue){
		System.out.println("id "+searchValue);
		List inputList = new ArrayList();
		Books input = bookSearch.getInputSearchName(searchValue);
		if(!ObjectUtils.isEmpty(input)){
			inputList.add(input.getAuthor());
			inputList.add(input.getAvailable());
			inputList.add(input.getTitle());
			inputList.add(input.getBookid());
		}
		System.out.println("inputList"+inputList);
		return inputList;
	}
	
	@RequestMapping(value ="/memberId", method = RequestMethod.GET, produces = MediaType.APPLICATION_JSON_VALUE)
	public List<String>getDataByMemberId(@RequestParam int memberid){
		List inputList = new ArrayList();
		Member input = bookSearch.getBookdtl(memberid);
		if(!ObjectUtils.isEmpty(input)){
			inputList.add(input.getName());
			inputList.add(input.getAddress());
			inputList.add(input.getExpirydate());
			inputList.add(input.getMembiD());
			inputList.add(input.getMembdate());
			inputList.add(input.getMembtype());
		}
		return inputList;
	}
	@RequestMapping(value ="/updatedBook/{idValue}", method = RequestMethod.POST, produces = MediaType.APPLICATION_JSON_VALUE)
	@ResponseBody
	public String updateBook(@PathVariable String idValue){
		String availableStatus="No";
		int input = bookSearch.updateBook(idValue,availableStatus);
		System.out.println(input+" output");
		return "successfully Booked";
	}
	
	@RequestMapping(value ="/ReturnBook/{idValue}", method = RequestMethod.POST, produces = MediaType.APPLICATION_JSON_VALUE)
	@ResponseBody
	public String ReturnBook(@PathVariable String idValue){
		String availableStatus="yes";
		int input = bookSearch.updateBook(idValue,availableStatus);
		System.out.println(input+" output");
		return "successfully Booked";
	}
	@RequestMapping(value ="/getAllData", method = RequestMethod.GET, produces = MediaType.APPLICATION_JSON_VALUE)
	@ResponseBody
	public List<Books> getAllData(){
		System.out.println(" output all data");
		List<Books> input = bookSearch.getAllBooks();
		System.out.println(" output all data"+input);
		return input;
	}
	
	
	@RequestMapping(value ="/memberRegistration/{memberName}/{memberAddress}/{memberType}", method = RequestMethod.GET, produces = MediaType.APPLICATION_JSON_VALUE)
	@ResponseBody
	public int memberRegistration(@PathVariable String memberName,@PathVariable String memberAddress,@PathVariable String memberType){
		
	      Date now = new Date();
	      Calendar cal = Calendar.getInstance();
	      Date today = cal.getTime();
	      cal.add(Calendar.YEAR, 1); // to get previous year add -1
	      Date next = cal.getTime();
	      
	     
	     // DateFormat df = new SimpleDateFormat("DD-MM-yyyy");
	      //String nextYear = df.format(next);
	     // String fromDate = df.format(now);
	      
		Member register=new Member();
			register.setName(memberName);
			register.setAddress(memberAddress);
			register.setMembtype(memberType);
			register.setMembdate(now);
			register.setExpirydate(next);
			
			 bookSearch.register(register);
		return 1;
	}
}
