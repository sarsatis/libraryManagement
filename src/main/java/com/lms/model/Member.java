package com.lms.model;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotNull;

import java.io.Serializable;
import java.util.Date;


/**
 * @author nitrawat
 *
 */

@Entity
@Table(name = "Member")
public class Member implements Serializable{

	
	/**
	 * 
	 */
	private static final long serialVersionUID = 1L;

	@Id
	@Column(name = "Memb_ID")
	@GeneratedValue(strategy = GenerationType.AUTO)
	private long membiD;
	
	public long getMembiD() {
		return membiD;
	}

	public void setMembiD(long membiD) {
		this.membiD = membiD;
	}


	public Date getExpirydate() {
		return expirydate;
	}

	public void setExpirydate(Date expirydate) {
		this.expirydate = expirydate;
	}

	public Date getMembdate() {
		return membdate;
	}

	public void setMembdate(Date membdate) {
		this.membdate = membdate;
	}

	public String getName() {
		return name;
	}

	public void setName(String name) {
		this.name = name;
	}

	public String getAddress() {
		return address;
	}

	public void setAddress(String address) {
		this.address = address;
	}

	public String getMembtype() {
		return membtype;
	}

	public void setMembtype(String membtype) {
		this.membtype = membtype;
	}

	
	@Column(name = "Expiry_date")
	private Date expirydate;
	
	@NotNull
	@Column(name = "Name")
	private String name;
	
	@Column(name = "Address")
	private String address;
	
	@NotNull
	@Column(name = "Memb_type")
	private String membtype;
	
	@NotNull
	@Column(name = "Memb_date")
	private Date membdate;
	
	
}
