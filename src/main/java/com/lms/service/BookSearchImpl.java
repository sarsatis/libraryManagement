package com.lms.service;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.lms.dao.BookSearchDao;
import com.lms.dao.MemberBookSearchDao;
import com.lms.model.Books;
import com.lms.model.Member;


/**
 * @author nitrawat
 *
 */
@Service
public class BookSearchImpl implements BookSearch {

	@Autowired
	BookSearchDao bookSearchDao;
	
	@Autowired
	MemberBookSearchDao memberBookSearch;

	@Override
	public Books getInputSearch(String id) {
		// TODO Auto-generated method stub
		return bookSearchDao.getInputSearch(id);
	}

	@Override
	public Books getInputSearchName(String name) {
		// TODO Auto-generated method stub
		return bookSearchDao.getInputSearchName(name);
	}

	@Override
	public Member getBookdtl(int memberId) {
		// TODO Auto-generated method stub
		return memberBookSearch.getBookdtl(memberId);
	}

	@Override
	public int updateBook(String idValue,String availableStatus) {
		// TODO Auto-generated method stub
		String avail=availableStatus;
		 return bookSearchDao.UpdateAvialiableBook(idValue,avail);
	}

	@Override
	public List<Books> getAllBooks() {
		// TODO Auto-generated method stub
		return bookSearchDao.getAllBooksData();
	}

	@Override
	public void register(Member register) {
		// TODO Auto-generated method stub
		 memberBookSearch.save(register);
	}


	
}
