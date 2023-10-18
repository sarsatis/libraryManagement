package com.lms.dao;

import java.io.Serializable;
import java.util.List;


import jakarta.transaction.Transactional;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.CrudRepository;
import org.springframework.data.repository.query.Param;

import com.lms.model.Books;
import com.lms.service.BookSearch;


/**
 * @author nitrawat
 *
 */
public interface BookSearchDao extends CrudRepository<Books, Serializable>{
	
	
	
	
	@Query("SELECT bookdtls FROM Books bookdtls where bookdtls.bookid= :id")
	public Books getInputSearch(@Param("id")final String id);
	
	@Query("SELECT bookdetails FROM Books bookdetails where bookdetails.title= :name")
	public Books getInputSearchName(@Param("name")final String name);
	
	@Modifying
	@Transactional
	@Query("UPDATE Books book SET book.available =:avail WHERE book.bookid =:idValue")
	public int UpdateAvialiableBook(@Param("idValue")final String idValue,@Param("avail")final String avail);
	
	@Query("SELECT booklist as booklist FROM Books booklist")
	public List<Books> getAllBooksData();
}