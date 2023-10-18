package com.lms.service;

import java.util.List;

import com.lms.model.Books;
import com.lms.model.Member;

/**
 * @author nitrawat
 *
 */
public interface BookSearch {
	public Books getInputSearch(String id);
	public Books getInputSearchName(String name);
	public Member getBookdtl(int memberId);
	public int updateBook(String idValue,String availableStatus);
	public List<Books> getAllBooks();
	public void register(Member register);
	
	
	
}
