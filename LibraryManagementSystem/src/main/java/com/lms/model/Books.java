package com.lms.model;

import javax.persistence.Column;
import javax.persistence.Entity;
import javax.persistence.GeneratedValue;
import javax.persistence.GenerationType;
import javax.persistence.Id;
import javax.persistence.Table;
import javax.validation.constraints.NotNull;

/**
 * @author nitrawat
 *
 */
@Entity
@Table(name = "Books")
public class Books implements java.io.Serializable {

	/**
	 * 
	 */
	private static final long serialVersionUID = 1L;
	@Id
	@Column(name = "Book_ID")
	@GeneratedValue(strategy = GenerationType.AUTO)
	private String bookid;
	
	@Column(name = "Author")
	private String author;
	

	@Column(name = "title")
	private String title;
	
	@Column(name = "Price")
	private String price;
	
	@Column(name = "Available")
	private String available;
	
	@Column(name = "Pub_ID")
	private String pub_ID;


	public String getBookid() {
		return bookid;
	}

	public void setBookid(String bookid) {
		this.bookid = bookid;
	}

	public String getAuthor() {
		return author;
	}

	public void setAuthor(String author) {
		this.author = author;
	}

	public String getTitle() {
		return title;
	}

	public void setTitle(String title) {
		this.title = title;
	}

	public String getPrice() {
		return price;
	}

	public void setPrice(String price) {
		this.price = price;
	}

	public String getAvailable() {
		return available;
	}

	public void setAvailable(String available) {
		this.available = available;
	}
	
	
	public String getPub_ID() {
		return pub_ID;
	}

	public void setPub_ID(String pub_ID) {
		this.pub_ID = pub_ID;
	}


}
