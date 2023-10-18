package com.lms.dao;

import java.io.Serializable;

import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.CrudRepository;
import org.springframework.data.repository.query.Param;

import com.lms.model.Books;
import com.lms.model.Member;

public interface MemberBookSearchDao extends CrudRepository<Member, Serializable>{

	
	@Query("SELECT bookdetails FROM Member bookdetails where bookdetails.membiD= :memberId")
	public Member getBookdtl(@Param("memberId")final long memberId);

}
